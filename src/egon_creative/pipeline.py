from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
from pathlib import Path
import time
import uuid

from PIL import Image, ImageChops, ImageStat

from . import media
from .process import Deadline, probe
from .store import canonical, file_hash
from .storyboard import validate


@contextmanager
def render_lock(path, deadline):
    with Path(path).open("a") as lock:
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                deadline.remaining()
                time.sleep(.1)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def animated(settings, timeline, folder, deadline):
    frames = folder / "frames"
    name = "render_focus.py" if timeline.get("visual_style") == "focus_explainer_v2" else "render_scene.py"
    script = Path(__file__).parent / "blender" / name
    with render_lock(settings.state_dir / "blender.lock", deadline):
        deadline.run([settings.blender, "--background", "--factory-startup", "--python-exit-code", "1", "--python", script,
                      "--", "--timeline", folder / "timeline.json", "--output", frames,
                      "--asset-dir", settings.state_dir / "assets", "--fps", str(settings.animation_fps), "--engine", settings.render_engine], folder / "blender.log")
    actual = sorted(frames.glob("frame-*.png"))
    expected = math.ceil(timeline["duration"] * settings.animation_fps)
    if len(actual) != expected:
        raise RuntimeError(f"Blender frame count mismatch: {len(actual)}/{expected}")
    deadline.run([settings.ffmpeg, "-v", "error", "-y", "-framerate", str(settings.animation_fps), "-i", frames / "frame-%04d.png",
                  "-t", str(timeline["duration"]), "-r", str(settings.output_fps), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", folder / "animation.mp4"], folder / "render.log")
    return actual


def real_footage(store, settings, timeline, folder, deadline):
    clips = []
    for i, shot in enumerate(timeline["shots"]):
        with store.connect() as con:
            asset = con.execute("SELECT * FROM assets WHERE id=? AND kind IN ('real_footage','flow_manual')", (shot.get("asset_id"),)).fetchone()
        if not asset or asset["kind"] != "real_footage":
            raise ValueError("Real footage must reference registered real_footage, not an animation or Flow clip")
        path = Path(asset["path"])
        if file_hash(path) != asset["sha256"]:
            raise ValueError("Footage changed since asset registration")
        info = probe(settings.ffprobe, path, deadline)
        start = float(shot.get("source_in_seconds", 0))
        if not math.isfinite(start) or start < 0 or start + shot["duration"] > float(info["format"]["duration"]) + .02:
            raise ValueError("Footage is too short for this shot. Never fabricate extra brewing action by silent looping.")
        target = folder / f"real-shot-{i:02d}.mp4"
        deadline.run([settings.ffmpeg, "-v", "error", "-y", "-ss", str(start), "-i", path, "-t", str(shot["duration"]),
                      "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1", "-an", "-r", str(settings.output_fps),
                      "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", target], folder / "render.log")
        clips.append(target)
    media.concat_file(folder / "real-clips.ffconcat", clips)
    deadline.run([settings.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", folder / "real-clips.ffconcat", "-c", "copy", folder / "animation.mp4"], folder / "render.log")
    return []


def quality(settings, doc, timeline, folder, result, raw_frames, deadline, logo):
    info = probe(settings.ffprobe, result, deadline)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    duration = float(info["format"]["duration"])
    if not video or (video["width"], video["height"]) != (1080, 1920) or not 30 <= duration <= 60.1:
        raise RuntimeError("Output dimension/duration gate failed")
    if not audio or video["codec_name"] != "h264" or audio["codec_name"] != "aac":
        raise RuntimeError("H264/AAC delivery gate failed")
    if abs(duration - timeline["duration"]) > .15:
        raise RuntimeError("Encoded duration differs from approved narration timeline")
    if doc.get('visual_style')=='cartoon_explainer_v3' and int(video.get('nb_frames',0))!=math.ceil(timeline['duration']*settings.output_fps):
        raise RuntimeError('Full cartoon episode encoded frame count mismatch')
    deadline.run([settings.ffmpeg, "-v", "error", "-i", result, "-f", "null", "-"], folder / "decode-check.log")
    changed_pairs, comparisons = 0, 0
    if raw_frames:
        picks = [raw_frames[round(i * (len(raw_frames) - 1) / 11)] for i in range(12)]
        previous = None
        for i, path in enumerate(picks):
            with Image.open(path) as im:
                current = im.convert("RGB").crop((80, 540, 1000, 1400))
                current.thumbnail((230, 215))
                if previous is not None:
                    comparisons += 1
                    changed_pairs += int(sum(ImageStat.Stat(ImageChops.difference(previous, current)).mean) > .25)
                previous = current.copy()
        if changed_pairs < comparisons // 2:
            raise RuntimeError("Original 3D motion gate failed; metadata hashes alone are not proof of animation")
    if not timeline["captions"] or not (folder / "captions.srt").is_file() or not (folder / "captions.mov").is_file():
        raise RuntimeError("Caption layer missing")
    # Local voice must contain an actual signal, not just silence with a nonzero duration.
    import wave, array
    with wave.open(str(folder / "voiceover.wav")) as wav:
        values = array.array("h", wav.readframes(wav.getnframes()))
        if not values or max(abs(v) for v in values) < 128:
            raise RuntimeError("Indonesian narration is silent")
    if logo and file_hash(logo["path"]) != logo["sha256"]:
        raise RuntimeError("Canonical logo bytes changed during rendering")
    qa = {"status": "PASS", "width": 1080, "height": 1920, "duration_seconds": duration,
          "video_codec": video["codec_name"], "audio_codec": audio["codec_name"],
          "encoded_fps": video["avg_frame_rate"], "native_animation_fps": settings.animation_fps if doc["kind"] == "animated" else None,
          "motion_changed_pairs": changed_pairs, "motion_comparisons": comparisons,
          "full_file_decode": "PASS", "burned_in_captions": True,
          "caption_alignment": timeline["caption_alignment"], "indonesian_local_tts": timeline["tts"],
          "brand_status": "PASS" if logo else "BLOCKED_CANONICAL_LOGO",
          "logo_sha256": logo["sha256"] if logo else None, "source_gate": "PASS",
          "visual_review": "HUMAN_REVIEW_REQUIRED", "technical_pass_is_visual_approval": False,
          "data_class": doc["data_class"], "deployed": False, "published": False,
          "known_paid_api_idr": 0, "output_sha256": file_hash(result)}
    qa["visual_style"] = doc.get("visual_style", "legacy_studio")
    if doc.get('visual_style')=='cartoon_explainer_v3':
        qa['actual_encoded_frames']=int(video['nb_frames'])
        qa['review_samples']=len(raw_frames)
        qa['delivery_scope']=doc.get('delivery_scope','FULL_EPISODE')
    if (folder / "logo-display.json").is_file():
        qa["logo_display"] = json.loads((folder / "logo-display.json").read_text())
    (folder / "QA.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2))
    return qa


def worker_once(store, settings):
    job_id = store.claim("local-" + uuid.uuid4().hex[:12])
    if not job_id:
        return {"status": "IDLE"}
    job = store.job(job_id)
    doc = store.storyboard(job_id)
    deadline, reserved = Deadline(settings.max_job_seconds), False
    folder = settings.state_dir / "jobs" / job_id / f"attempt-{job['attempts']:03d}"
    folder.mkdir(parents=True, exist_ok=False)
    try:
        validate(doc)
        logo = store.canonical_logo()
        if not logo and doc["data_class"] == "PRODUCTION":
            raise ValueError("BLOCKED_CANONICAL_LOGO: register the owner-provided unmodified asset")
        expected_logo = doc.get("canonical_logo_sha256")
        if (expected_logo and (not logo or expected_logo != logo["sha256"])) or (doc["data_class"] == "PRODUCTION" and not expected_logo):
            raise ValueError("Canonical logo must match the versioned storyboard asset hash")
        if logo and Path(logo["path"]).suffix.lower() not in {".png", ".webp"}:
            raise ValueError("Use an owner-provided raster PNG/WebP logo; no automatic SVG redesign/conversion")
        if doc["kind"] == "static":
            (folder / "LEGACY_HANDOFF.json").write_text(canonical(doc))
            raise ValueError("STATIC_HANDOFF_REQUIRED: use the existing Creative static workflow; no paid generation is triggered")
        store.reserve(job_id, settings.reserved_local_idr, settings.max_cost_idr)
        reserved = True
        (folder / "storyboard.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2))
        (folder / "prompt.txt").write_text(doc["visual_prompt"])
        timeline = media.speech(settings, doc, folder, deadline)
        media.check_layout(doc, timeline)
        if doc['kind']=='animated' and doc.get('visual_style')=='cartoon_explainer_v3':
            from .cartoon_full import animated as cartoon_animated
            frames=cartoon_animated(store,settings,doc,timeline,folder,deadline)
        else:
            frames = animated(settings, timeline, folder, deadline) if doc["kind"] == "animated" else real_footage(store, settings, timeline, folder, deadline)
        result = media.edit(settings, doc, timeline, folder, deadline, logo)
        qa = quality(settings, doc, timeline, folder, result, frames, deadline, logo)
        store.finish(job_id, "DESIGN_REVIEW", result, qa)
        return {"job_id": job_id, "status": "DESIGN_REVIEW", "output": str(result), "qa": qa}
    except Exception as exc:
        status = "BLOCKED" if isinstance(exc, (ValueError, FileNotFoundError)) else "FAILED"
        store.finish(job_id, status, error=str(exc))
        (folder / "FAILURE.json").write_text(json.dumps({"status": status, "error": str(exc), "elapsed_seconds": deadline.elapsed}, indent=2))
        return {"job_id": job_id, "status": status, "error": str(exc), "folder": str(folder)}
    finally:
        if reserved:
            store.settle(job_id, deadline.elapsed, settings.watts_estimate, settings.tariff_idr_kwh)
