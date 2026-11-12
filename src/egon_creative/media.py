"""Local Indonesian speech, original SFX and native FFmpeg overlays."""
import array
import hashlib
import io
import json
import math
from pathlib import Path
import platform
import random
import shutil
import textwrap
import wave

from PIL import Image, ImageChops, ImageCms, ImageDraw, ImageFont

from .process import probe


def concat_file(path, files, durations=None):
    def quote(p):
        return "'" + str(Path(p).resolve()).replace("'", "'\\''") + "'"
    rows = ["ffconcat version 1.0"]
    for i, item in enumerate(files):
        rows.append("file " + quote(item))
        if durations is not None:
            rows.append(f"duration {durations[i]:.8f}")
    if durations is not None:
        rows.append("file " + quote(files[-1]))
    Path(path).write_text("\n".join(rows) + "\n")


def speech(settings, doc, folder, deadline):
    if platform.system() != "Darwin" or not shutil.which("say"):
        raise RuntimeError("Local Indonesian TTS unavailable. Install a local Indonesian TTS adapter; no cloud fallback.")
    audio = folder / "audio"
    audio.mkdir()
    records, shots = [], []
    for si, shot in enumerate(doc["shots"]):
        for ci, text in enumerate(shot["narration"]):
            stem = audio / f"s{si:02d}-c{ci:02d}"
            stem.with_suffix(".txt").write_text(text, encoding="utf-8")
            aiff = stem.with_suffix(".aiff")
            deadline.run(["say", "-v", settings.tts_voice, "-r", "170", "-f", stem.with_suffix(".txt"), "-o", aiff], folder / "render.log")
            duration = float(probe(settings.ffprobe, aiff, deadline)["format"]["duration"])
            if duration <= .1:
                raise RuntimeError("TTS produced empty audio")
            records.append({"shot": si, "text": text, "voice_seconds": duration, "source": str(aiff)})
    minimum = sum(r["voice_seconds"] + .15 for r in records)
    explicit = all('duration_seconds' in s for s in doc['shots'])
    extras = {}
    if explicit:
        for si, shot in enumerate(doc['shots']):
            selected = [r for r in records if r['shot'] == si]
            needed = sum(r['voice_seconds'] + .15 for r in selected)
            if needed > shot['duration_seconds']:
                raise ValueError(f'Rewrite narration in shot {si+1}: measured speech exceeds its explicit duration')
            extras[si] = (shot['duration_seconds'] - needed) / len(selected)
    duration = doc['target_seconds'] if explicit else max(doc["target_seconds"], minimum, 30)
    if duration > 60:
        raise ValueError("Narration exceeds 60 seconds; rewrite the script before rendering")
    extra = (duration - minimum) / len(records)
    clock, wavs = 0.0, []
    for i, r in enumerate(records):
        span = r["voice_seconds"] + .15 + (extras[r['shot']] if explicit else extra)
        target = audio / f"part-{i:02d}.wav"
        deadline.run([settings.ffmpeg, "-v", "error", "-y", "-i", r["source"], "-af", "apad", "-t", str(span), "-ar", "48000", "-ac", "1", target], folder / "render.log")
        r.update({"start": clock, "end": clock + span})
        clock += span
        wavs.append(target)
    concat_file(audio / "parts.ffconcat", wavs)
    result = folder / "voiceover.wav"
    deadline.run([settings.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", audio / "parts.ffconcat", "-c:a", "pcm_s16le", result], folder / "render.log")
    for si, shot in enumerate(doc["shots"]):
        chunks = [r for r in records if r["shot"] == si]
        shots.append({**shot, "start": chunks[0]["start"], "end": chunks[-1]["end"], "duration": chunks[-1]["end"] - chunks[0]["start"]})
    timeline = {"duration": clock, "captions": records, "shots": shots,
                "visual_style": doc.get("visual_style", "legacy_studio"),
                "tts": {"provider": "macOS say", "voice": settings.tts_voice, "language": "id-ID", "words_per_minute_setting": 170, "paid_api_idr": 0},
                "caption_alignment": "Measured per-chunk TTS durations, not word-level forced alignment"}
    (folder / "timeline.json").write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    return timeline


def font(size, bold=True):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Rounded Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Install a local TrueType font for legible captions")


def wrapped(text, draw, fnt, max_width=830):
    lines, current = [], ""
    for word in text.split():
        trial = (current + " " + word).strip()
        if draw.textbbox((0, 0), trial, font=fnt)[2] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def check_layout(doc, timeline):
    """Reject unreadable copy before spending time on the 3D render."""
    draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    if draw.textbbox((0, 0), doc["title"], font=font(35))[2] > 950:
        raise ValueError("Rewrite the title to fit the vertical safe area")
    motion = doc.get("visual_style") == "focus_explainer_v2"
    cartoon = doc.get('visual_style') == 'cartoon_explainer_v3'
    for item in timeline["captions"]:
        if len(wrapped(item["text"], draw, font(54 if motion else 48))) > (2 if motion else 3):
            raise ValueError("Rewrite subtitle chunk: more than three readable lines")
    for shot in doc["shots"]:
        if cartoon:
            if len(wrapped(shot.get('label', ''), draw, font(76), 880)) > 2:
                raise ValueError('Rewrite cartoon headline to fit two readable lines')
        elif draw.textbbox((0, 0), shot.get("label", "EKSPLORASI KOPI"), font=font(60 if motion else 44))[2] > 850:
            raise ValueError("Rewrite scene label to fit the vertical safe area")


def overlays(settings, doc, timeline, folder, deadline, has_logo):
    check_layout(doc, timeline)
    if doc.get('visual_style') == 'cartoon_explainer_v3':
        from .cartoon_full import overlays as cartoon_overlays
        return cartoon_overlays(settings, doc, timeline, folder, deadline, has_logo)
    if doc.get("visual_style") == "focus_explainer_v2":
        from .motion_typography import overlays as focus_overlays
        return focus_overlays(settings, doc, timeline, folder, deadline, has_logo)
    overlays_dir = folder / "overlays"
    overlays_dir.mkdir()
    files, spans = [], []
    for i, item in enumerate(timeline["captions"]):
        im = Image.new("RGBA", (1080, 1920))
        draw = ImageDraw.Draw(im)
        shot = doc["shots"][item["shot"]]
        label = shot.get("label", "EKSPLORASI KOPI")
        label_font = font(44)
        if draw.textbbox((0, 0), label, font=label_font)[2] > 850:
            raise ValueError("Rewrite scene label to fit the vertical safe area")
        draw.rounded_rectangle((110, 465, 970, 555), radius=30, fill="#d9f230")
        draw.text((540, 484), label, font=label_font, anchor="mt", fill="#35205f")
        # Original doodle accents, generated as layout shapes rather than copied artwork.
        draw.line([(920, 590), (945, 610), (915, 630)], fill="#ff5012", width=9)
        draw.arc((110, 580, 190, 660), 210, 330, fill="#35205f", width=7)
        fnt = font(48)
        lines = wrapped(item["text"], draw, fnt)
        if len(lines) > 3:
            raise ValueError("Rewrite subtitle chunk: more than three readable lines")
        y = 1440
        draw.rounded_rectangle((88, y - 30, 992, y + len(lines) * 64 + 25), radius=28, fill=(49, 13, 75, 245))
        for n, line in enumerate(lines):
            draw.text((540, y + n * 64), line, font=fnt, anchor="mt", fill="#fff3db")
        path = overlays_dir / f"caption-{i:02d}.png"
        im.save(path)
        files.append(path)
        spans.append(item["end"] - item["start"])
    concat_file(overlays_dir / "captions.ffconcat", files, spans)
    deadline.run([settings.ffmpeg, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", overlays_dir / "captions.ffconcat", "-t", str(timeline["duration"]), "-r", str(settings.output_fps), "-c:v", "qtrle", "-pix_fmt", "argb", folder / "captions.mov"], folder / "render.log")
    brand = Image.new("RGBA", (1080, 1920))
    draw = ImageDraw.Draw(brand)
    if not has_logo:
        draw.rounded_rectangle((64, 110, 1016, 230), radius=24, fill="#f14c12")
        draw.text((540, 134), "UJI TEKNIS • LOGO RESMI", font=font(31), fill="#fff6e3", anchor="mt")
        draw.text((540, 182), "BELUM DIBERIKAN", font=font(31), fill="#fff6e3", anchor="mt")
    draw.text((540, 276 if not has_logo else 340), doc["title"], font=font(35), fill="#3a1258", anchor="mt")
    draw.text((540, 398), "EGON COFFEE • ANIMASI EDUKASI", font=font(23), fill="#3a1258", anchor="mt")
    draw.rounded_rectangle((82, 1730, 998, 1825), radius=22, fill="#3a1258")
    draw.text((540, 1742), "YOUR CUP. YOUR RULES.", font=font(35), fill="#fff3db", anchor="mt")
    draw.text((540, 1790), "@kopiegon", font=font(24), fill="#d9f230", anchor="mt")
    brand.save(folder / "brand-treatment.png")
    # SRT accompanies the burned-in caption layer for accessible manual editing.
    def stamp(v):
        ms = int(round(v * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"
    (folder / "captions.srt").write_text("\n\n".join(f"{i+1}\n{stamp(r['start'])} --> {stamp(r['end'])}\n{r['text']}" for i, r in enumerate(timeline["captions"])) + "\n")


def sfx(timeline, path):
    rate, rng = 48000, random.Random(42)
    samples = array.array("h", [0]) * int(math.ceil(timeline["duration"] * rate))
    for shot in timeline["shots"]:
        start = int(shot["start"] * rate)
        for i in range(int(.17 * rate)):
            if start + i >= len(samples):
                break
            t = i / rate
            env = math.sin(math.pi * t / .17) ** 2
            value = (math.sin(2 * math.pi * (620 - 900 * t) * t) * .016 + rng.uniform(-1, 1) * .003) * env
            samples[start + i] = int(value * 32767)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def logo_for_display(logo, folder):
    """Honor embedded ICC for video display while preserving the canonical master."""
    source = Path(logo["path"])
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if original_hash != logo["sha256"]:
        raise ValueError("Canonical logo changed before composition")
    result = source
    record = {"canonical_sha256": original_hash, "canonical_master_unchanged": True,
              "artistic_changes": False, "crop": False, "redraw": False,
              "display_conversion": "none; untagged source treated as sRGB"}
    with Image.open(source) as im:
        profile = im.info.get("icc_profile")
        if profile:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(profile))
            dst_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
            rgba = im.convert("RGBA")
            display = ImageCms.profileToProfile(rgba, src_profile, dst_profile,
                                              renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
                                              outputMode="RGBA", inPlace=False)
            if display.size != rgba.size or ImageChops.difference(display.getchannel("A"), rgba.getchannel("A")).getbbox():
                raise ValueError("Logo display conversion changed geometry or transparency")
            result = folder / "logo-display-srgb.png"
            display.save(result, icc_profile=dst_profile.tobytes())
            record.update({"source_profile": ImageCms.getProfileName(src_profile).strip(),
                           "display_profile": "sRGB", "display_conversion": "embedded ICC to sRGB",
                           "geometry_and_alpha_unchanged": True,
                           "display_sha256": hashlib.sha256(result.read_bytes()).hexdigest()})
    if hashlib.sha256(source.read_bytes()).hexdigest() != original_hash:
        raise ValueError("Canonical master changed during display conversion")
    (folder / "logo-display.json").write_text(json.dumps(record, indent=2))
    return result


def edit(settings, doc, timeline, folder, deadline, logo):
    overlays(settings, doc, timeline, folder, deadline, bool(logo))
    sfx(timeline, folder / "sfx.wav")
    inputs = [settings.ffmpeg, "-v", "error", "-y", "-i", folder / "animation.mp4", "-i", folder / "captions.mov", "-loop", "1", "-i", folder / "brand-treatment.png", "-i", folder / "voiceover.wav", "-i", folder / "sfx.wav"]
    filters = ["[0:v]fps=24,setsar=1[base]", "[base][1:v]overlay=0:0:shortest=1[captioned]", "[captioned][2:v]overlay=0:0[branded]"]
    output = "branded"
    if logo:
        # ICC is a display transform, not an artistic palette change; the master stays byte-identical.
        inputs += ["-loop", "1", "-i", logo_for_display(logo, folder)]
        if doc.get("visual_style") in {"focus_explainer_v2", "cartoon_explainer_v3"}:
            filters += ["[5:v]scale=w=240:h=145:force_original_aspect_ratio=decrease[logo]", "[branded][logo]overlay=W-w-76:70[official]"]
        else:
            filters += ["[5:v]scale=w=350:h=220:force_original_aspect_ratio=decrease[logo]", "[branded][logo]overlay=(W-w)/2:110[official]"]
        output = "official"
    filters += [f"[{output}]format=yuv420p[vout]", "[3:a][4:a]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]"]
    result = folder / "EGON_REEL.mp4"
    deadline.run(inputs + ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]", "-t", str(timeline["duration"]), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", result], folder / "render.log")
    return result
