import argparse
import json
from pathlib import Path
import platform
import shutil
import subprocess

from .config import Settings
from .store import Store, file_hash


def doctor(settings):
    checks = {}
    for name in ["blender", "ffmpeg", "ffprobe"]:
        executable = getattr(settings, name)
        found = Path(executable).is_file() or shutil.which(executable)
        if found:
            try:
                flag = "--version" if name == "blender" else "-version"
                r = subprocess.run([executable, flag], capture_output=True, text=True, timeout=30)
                checks[name] = {"ok": r.returncode == 0, "version": r.stdout.splitlines()[0] if r.stdout else "unknown"}
            except (OSError, subprocess.TimeoutExpired):
                checks[name] = {"ok": False}
        else:
            checks[name] = {"ok": False}
    voice_ok = False
    if platform.system() == "Darwin" and shutil.which("say"):
        r = subprocess.run(["say", "-v", "?"], capture_output=True, text=True, timeout=15)
        voice_ok = any(line.startswith(settings.tts_voice + " ") and "id_ID" in line for line in r.stdout.splitlines())
    checks["indonesian_tts"] = {"ok": voice_ok, "voice": settings.tts_voice, "provider": "local macOS say"}
    checks["canonical_logo"] = {"ok": bool(Store(settings.db_path).canonical_logo()), "required_for_production": True}
    return {"checks": checks, "local_render_ready": all(checks[k]["ok"] for k in ["blender", "ffmpeg", "ffprobe", "indonesian_tts"]),
            "paid_api_default_idr": 0, "max_video_idr": settings.max_cost_idr, "state_dir": str(settings.state_dir), "deployed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="egon-creative")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ["init", "doctor", "queue", "work", "agents"]:
        sub.add_parser(name)
    p = sub.add_parser("plan")
    p.add_argument("--blocks", type=int, default=1)
    p = sub.add_parser("enqueue")
    p.add_argument("storyboard", type=Path)
    p = sub.add_parser("retry")
    p.add_argument("job_id")
    p = sub.add_parser("approve")
    p.add_argument("job_id")
    p.add_argument("--by", required=True)
    p.add_argument("--ack-human", action="store_true")
    p.add_argument("--ack-visual", action="store_true", help="Human has reviewed the complete final video, subtitles, voice and pacing")
    p = sub.add_parser("register-logo")
    p.add_argument("path", type=Path)
    p.add_argument("--sha256", required=True)
    p.add_argument("--owner-confirmed", action="store_true")
    p.add_argument("--source-ref", required=True)
    p = sub.add_parser("register-footage")
    p.add_argument("path", type=Path)
    p.add_argument("--source-ref", required=True)
    p = sub.add_parser("metrics")
    p.add_argument("job_id")
    p.add_argument("measurement", type=Path)
    p = sub.add_parser("record-cost")
    p.add_argument("job_id")
    p.add_argument("--amount-idr", type=float, required=True)
    p.add_argument("--category", choices=["manual_local_preview", "manual_external_generation"], required=True)
    p.add_argument("--basis", choices=["ESTIMATE", "KNOWN_ACTUAL"], required=True)
    p.add_argument("--source-ref", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8765)
    p = sub.add_parser("gemini-draft")
    p.add_argument("public_brief")
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("flow-export")
    p.add_argument("storyboard", type=Path)
    p.add_argument("target", type=Path)
    p = sub.add_parser("flow-import")
    p.add_argument("path", type=Path)
    p.add_argument("--source-ref", required=True)
    args = parser.parse_args(argv)
    settings = Settings.from_env()
    store = Store(settings.db_path)
    if args.command == "init":
        result = {"db": str(settings.db_path), "schema_version": 2, "business_schema_modified": False}
    elif args.command == "doctor":
        result = doctor(settings)
    elif args.command == "agents":
        from .agents import registry
        result = registry()
    elif args.command == "plan":
        from .storyboard import plan_mix
        result = {"mix": {"animated": 70, "real_footage": 20, "static": 10}, "units": plan_mix(args.blocks), "daily_quota_assumed": False}
    elif args.command == "enqueue":
        result = {"job_id": store.enqueue(json.loads(args.storyboard.read_text()))}
    elif args.command == "work":
        from .pipeline import worker_once
        result = worker_once(store, settings)
    elif args.command == "queue":
        result = store.snapshot()
    elif args.command == "retry":
        store.retry(args.job_id)
        result = {"job_id": args.job_id, "status": "QUEUED", "prior_costs_preserved": True}
    elif args.command == "approve":
        result = {"approval_id": store.approve(args.job_id, args.by, args.ack_human, args.ack_visual), "published": False}
    elif args.command == "register-logo":
        if not args.owner_confirmed or file_hash(args.path) != args.sha256:
            raise ValueError("Owner confirmation and exact original file hash required; never use a generated poster logo")
        result = {"asset_id": store.register_asset(args.path, "logo", args.source_ref, True)}
    elif args.command == "register-footage":
        result = {"asset_id": store.register_asset(args.path, "real_footage", args.source_ref)}
    elif args.command == "metrics":
        from .performance import ingest
        result = {"measurement_id": ingest(store, args.job_id, json.loads(args.measurement.read_text()))}
    elif args.command == "record-cost":
        result = {**store.record_expense(args.job_id, args.amount_idr, args.category, args.basis, args.source_ref), "provider_called": False, "payment_made": False}
    elif args.command == "serve":
        from .dashboard import serve
        serve(store, args.port)
        return
    elif args.command == "gemini-draft":
        from .gemini import draft
        result = draft(args.public_brief)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
        result = {"draft": str(args.output), "source_and_approval_review": "REQUIRED"}
    elif args.command == "flow-export":
        from .manual_flow import export_brief
        result = {"folder": export_brief(json.loads(args.storyboard.read_text()), args.target), "api_used": False}
    elif args.command == "flow-import":
        from .manual_flow import import_clip
        result = {"asset_id": import_clip(store, settings, args.path, args.source_ref), "api_used": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command == "work" and result["status"] in {"BLOCKED", "FAILED"}:
        return 2
    return 0
