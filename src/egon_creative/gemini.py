"""Optional draft-only Gemini adapter. No API key or paid fallback is accepted."""
from datetime import datetime
import json
import os
import re
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo


class FreeTierBlocked(RuntimeError):
    pass


def request_json(url, token, project, payload=None):
    headers = {"Authorization": "Bearer " + token, "x-goog-user-project": project}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not log response bodies, request URLs containing credentials, or tokens.
        raise FreeTierBlocked(f"Google HTTP {exc.code}; cloud draft stopped, no paid fallback") from None


def draft(public_brief, transport=request_json):
    if os.environ.get("EGON_GEMINI_ENABLED") != "free-only":
        raise FreeTierBlocked("Gemini disabled by default; local pipeline needs no cloud account")
    project = os.environ.get("EGON_GEMINI_PROJECT", "")
    model = os.environ.get("EGON_GEMINI_MODEL", "")
    token = os.environ.get("EGON_GOOGLE_OAUTH_TOKEN", "")
    verified = os.environ.get("EGON_GEMINI_MODEL_FREE_VERIFIED_ON", "")
    if not token or not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project) or not re.fullmatch(r"gemini-[a-zA-Z0-9.-]+", model):
        raise FreeTierBlocked("Explicit OAuth project and currently free-eligible model required")
    if verified != datetime.now(ZoneInfo("Asia/Jakarta")).date().isoformat():
        raise FreeTierBlocked("Confirm today's official model free-tier eligibility before this optional draft call")
    billing = transport(f"https://cloudbilling.googleapis.com/v1/projects/{project}/billingInfo", token, project)
    if billing.get("projectId") != project or billing.get("billingEnabled") is not False or billing.get("billingAccountName"):
        raise FreeTierBlocked("Project billing is enabled, linked, mismatched or unknown; no generation request sent")
    prompt = (
        "Draft an original beginner-friendly Indonesian EGON coffee media storyboard for Gen Z as JSON. "
        "Build curiosity through coffee history, culture, practical knowledge or sourced industry insights, not a hard-sell product ad. "
        "Start with the discovery/question, use short everyday sentences and end with a useful save/share/explore invitation. "
        "Use original 3D cartoon direction, never copy CTMVerse artwork. Do not claim EGON physical lab tests. "
        "Never invent product specifications, sources or approvals. Return schema_version=1, kind=animated, "
        "title, language=id-ID, target_seconds=40, visual_prompt, and five shots with scene from "
        "cherry/green/roast/brew/explore, narration as short text chunks, claim_ids. "
        "This draft will be independently researched and reviewed. Public brief: " + public_brief
    )
    result = transport(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", token, project,
                       {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 2400}})
    text = result["candidates"][0]["content"]["parts"][0]["text"]
    doc = json.loads(text)
    doc.update({"schema_version": 1, "data_class": "PRODUCTION", "language": "id-ID", "egon_test_ref": None,
                "gates": {k: "REVIEW_REQUIRED" for k in ["EDITORIAL_FIT", "INSPIRATION_FIT", "TRUTHFUL_AUTHORITY", "NOVELTY"]},
                "research_reviewed_by": None, "novelty_review": {}, "sources": [],
                "cloud_provenance": {"project_billing_enabled": False, "model": model, "model_free_verified_on": verified}})
    return doc
