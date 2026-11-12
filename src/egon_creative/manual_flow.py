import json
from pathlib import Path

from .process import probe


def export_brief(doc, target):
    target = Path(target)
    target.mkdir(parents=True, exist_ok=False)
    (target / "storyboard.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2))
    text = "# Optional Google Flow manual handoff\n\nNo Flow API is configured. Open Flow yourself, review its terms/credits, and import only owned assets. Any external paid use needs separate approval and cost recording; it is not part of the default zero-paid local pipeline.\n\n"
    text += doc["visual_prompt"] + "\n\n"
    for i, shot in enumerate(doc["shots"], 1):
        text += f"## Shot {i}: {shot['scene']}\n\n" + " ".join(shot["narration"]) + "\n\n"
    text += "No EGON logo may be generated inside Flow. Add the registered original canonical asset during local final editing. Generated media is animation, never real brewing documentation.\n"
    (target / "FLOW_MANUAL_BRIEF.md").write_text(text)
    return str(target)


def import_clip(store, settings, path, provenance):
    path = Path(path).expanduser().resolve(strict=True)
    info = probe(settings.ffprobe, path)
    if not any(s.get("codec_type") == "video" for s in info["streams"]):
        raise ValueError("Manual import has no video stream")
    return store.register_asset(path, "flow_manual", provenance)
