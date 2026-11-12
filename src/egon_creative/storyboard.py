from datetime import date, datetime
import math
import re
from zoneinfo import ZoneInfo

GATES = ("EDITORIAL_FIT", "INSPIRATION_FIT", "TRUTHFUL_AUTHORITY", "NOVELTY")
KINDS = ("animated", "real_footage", "static")
SCENES = ("cherry", "green", "roast", "grind", "brew", "explore")


def plan_mix(blocks=1):
    if not isinstance(blocks, int) or not 1 <= blocks <= 100:
        raise ValueError("Plan 1–100 blocks, not an implicit daily publishing quota")
    return [{"unit": n * 10 + i + 1, "kind": k, "status": "TOPIC_REVIEW"}
            for n in range(blocks)
            for i, k in enumerate(["animated"] * 7 + ["real_footage"] * 2 + ["static"])]


def validate(doc):
    if doc.get("schema_version") != 1 or doc.get("kind") not in KINDS:
        raise ValueError("Unsupported storyboard version or content kind")
    if doc.get("data_class") not in {"ENGINEERING_FIXTURE", "PRODUCTION"}:
        raise ValueError("Explicit fixture/production classification required")
    if not isinstance(doc.get("title"), str) or not doc["title"].strip():
        raise ValueError("Missing title")
    if doc.get("language") != "id-ID":
        raise ValueError("Indonesian narration is required")
    style = doc.get("visual_style", "legacy_studio")
    if style not in {"legacy_studio", "focus_explainer_v2", "cartoon_explainer_v3"}:
        raise ValueError("Unknown visual style")
    if style in {"focus_explainer_v2", "cartoon_explainer_v3"} and doc["kind"] != "animated":
        raise ValueError("Focus 3D explainer style requires animated content; real footage uses its verified route")
    duration = doc.get("target_seconds", 40)
    if not isinstance(duration, (float, int)) or not math.isfinite(duration) or not 30 <= duration <= 60:
        raise ValueError("Default pilot duration must be 30–60 seconds")
    if doc.get("egon_test_ref") is not None:
        raise ValueError("This release cannot validate physical EGON lab test logs")
    if not isinstance(doc.get("visual_prompt"), str) or not doc["visual_prompt"].strip():
        raise ValueError("Versioned original visual instructions are required")
    for gate in GATES:
        if doc.get("gates", {}).get(gate) != "PASS":
            raise ValueError(f"Pre-render review required: {gate}")
    sources = doc.get("sources", [])
    if not sources:
        raise ValueError("Source evidence is required even for the engineering script")
    ids = set()
    for src in sources:
        if not src.get("opened") or not src.get("claim_ids") or not src.get("publisher"):
            raise ValueError("Each source must have opened evidence, claim IDs and a publisher")
        if not re.match(r"^https://[^\s]+$", src.get("url", "")):
            raise ValueError("Source URL must be HTTPS")
        checked = date.fromisoformat(src["checked_at"][:10])
        if checked > datetime.now(ZoneInfo("Asia/Jakarta")).date():
            raise ValueError("Source checked date is in the future")
        ids.update(src["claim_ids"])
    shots = doc.get("shots", [])
    if not 3 <= len(shots) <= 12:
        raise ValueError("Use 3–12 shots")
    if any('duration_seconds' in s for s in shots):
        durations = [s.get('duration_seconds') for s in shots]
        if any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0 for v in durations):
            raise ValueError('Explicit shot timing requires positive finite seconds on every shot')
        if abs(sum(durations) - duration) > .001:
            raise ValueError('Explicit shot timings must equal the episode target')
    for shot in shots:
        if shot.get("scene") not in SCENES:
            raise ValueError("Unknown reusable scene")
        if shot["scene"] == "grind" and style not in {"focus_explainer_v2", "cartoon_explainer_v3"}:
            raise ValueError("Grinding scene requires the focus explainer renderer")
        if style in {"focus_explainer_v2", "cartoon_explainer_v3"} and not all(shot.get("motion_plan", {}).get(k) for k in ["primary_action", "camera", "learning_purpose"]):
            raise ValueError("Focus explainer requires a purposeful motion plan per shot")
        chunks = shot.get("narration", [])
        if not isinstance(chunks, list) or not chunks or any(not isinstance(t, str) or not t.strip() for t in chunks):
            raise ValueError("Each shot needs explicit narration/subtitle chunks")
        text = " ".join(chunks)
        if len(text) > 600 or any(len(t) > 180 for t in chunks):
            raise ValueError("Keep narration chunks short enough for legible captions")
        if re.search(r"belum.{0,10}(?:uji|lab)|pakai bahasa|pakai bahasamu|hasil lab kami|sudah diuji EGON|kami membuktikan", text, re.I):
            raise ValueError("Unsupported lab authority or prohibited public filler")
        if not set(shot.get("claim_ids", [])).issubset(ids):
            raise ValueError("A shot cites unsupported claim IDs")
    if doc["data_class"] == "PRODUCTION":
        if not isinstance(doc.get("production_id"), str) or not doc["production_id"].strip():
            raise ValueError("Production needs a stable production_id across script/visual revisions")
        review = doc.get("novelty_review", {})
        if not review.get("reviewed_by") or not review.get("compared_records") or not review.get("reason"):
            raise ValueError("Production needs semantic novelty review, including ledger/draft comparisons")
        if not doc.get("research_reviewed_by"):
            raise ValueError("Production needs a named research review")
        if doc["kind"] == "real_footage" and any(not s.get("asset_id") for s in shots):
            raise ValueError("Real videos require registered footage per shot; never label animation as real")
    return doc
