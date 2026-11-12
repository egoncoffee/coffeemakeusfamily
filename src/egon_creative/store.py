"""A separate creative database. Never opens the Sheets/business database."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
import uuid


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(part)
    return h.hexdigest()


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS versions(
 hash TEXT PRIMARY KEY, kind TEXT NOT NULL, document TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, version_hash TEXT NOT NULL REFERENCES versions(hash),
 idempotency_key TEXT NOT NULL UNIQUE, kind TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','DESIGN_REVIEW','APPROVED','BLOCKED','FAILED')),
 data_class TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 worker_id TEXT, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,
 output_path TEXT, output_sha256 TEXT, qa_json TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS assets(
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL,
 provenance TEXT NOT NULL, canonical INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS costs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
 attempt INTEGER NOT NULL, category TEXT NOT NULL, amount_idr REAL NOT NULL CHECK(amount_idr>=0),
 basis TEXT NOT NULL CHECK(basis IN ('RESERVED','ESTIMATE','KNOWN_ACTUAL')),
 released INTEGER NOT NULL DEFAULT 0, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS approvals(
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES jobs(id), approver TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, output_sha256 TEXT NOT NULL, approved_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS metrics(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(id),
 observed_at TEXT NOT NULL, source_ref TEXT NOT NULL, document TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT REFERENCES jobs(id),
 action TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS queue_status ON jobs(status, created_at);
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)
            con.execute("INSERT OR IGNORE INTO schema_versions VALUES(1,?)", (now(),))
            columns = {r[1] for r in con.execute("PRAGMA table_info(jobs)")}
            if "video_id" not in columns:
                con.execute("ALTER TABLE jobs ADD COLUMN video_id TEXT")
                for row in con.execute("SELECT j.id,v.document FROM jobs j JOIN versions v ON j.version_hash=v.hash").fetchall():
                    doc = json.loads(row[1])
                    con.execute("UPDATE jobs SET video_id=? WHERE id=?", (self.video_id(doc), row[0]))
            con.execute("CREATE INDEX IF NOT EXISTS job_video ON jobs(video_id)")
            con.execute("INSERT OR IGNORE INTO schema_versions VALUES(2,?)", (now(),))

    @staticmethod
    def video_id(doc):
        return doc.get("production_id") or "VIDEO-" + digest({"title": doc["title"], "kind": doc["kind"]})[:24]

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        try:
            yield con
            con.commit()
        except BaseException:
            con.rollback()
            raise
        finally:
            con.close()

    def event(self, con, job_id, action, detail):
        con.execute("INSERT INTO events(job_id,action,detail,created_at) VALUES(?,?,?,?)",
                    (job_id, action, canonical(detail), now()))

    def enqueue(self, storyboard):
        from .storyboard import validate
        validate(storyboard)
        sha = digest(storyboard)
        job_id = "EGON-VIDEO-" + sha[:16]
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO versions VALUES(?,?,?,?)",
                        (sha, "storyboard", canonical(storyboard), now()))
            # A recipe/shot/prompt change creates a different immutable input version.
            cur = con.execute("INSERT OR IGNORE INTO jobs(id,version_hash,idempotency_key,kind,status,data_class,created_at,video_id) VALUES(?,?,?,?,?,?,?,?)",
                              (job_id, sha, sha, storyboard["kind"], "QUEUED", storyboard["data_class"], now(), self.video_id(storyboard)))
            if cur.rowcount:
                self.event(con, job_id, "ENQUEUED", {"version": sha})
        return job_id

    def job(self, job_id):
        with self.connect() as con:
            row = con.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            return dict(row)

    def storyboard(self, job_id):
        with self.connect() as con:
            row = con.execute("SELECT v.document FROM jobs j JOIN versions v ON j.version_hash=v.hash WHERE j.id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            return json.loads(row[0])

    def claim(self, worker_id):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT id FROM jobs WHERE status='QUEUED' ORDER BY created_at,id LIMIT 1").fetchone()
            if not row:
                return None
            con.execute("UPDATE jobs SET status='RUNNING',worker_id=?,started_at=?,attempts=attempts+1,error=NULL WHERE id=? AND status='QUEUED'",
                        (worker_id, now(), row[0]))
            self.event(con, row[0], "CLAIMED", {"worker": worker_id})
            return row[0]

    def reserve(self, job_id, amount, ceiling):
        if not math.isfinite(amount) or amount < 0 or not math.isfinite(ceiling):
            raise ValueError("Negative reservation")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT attempts,status,video_id FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row[1] != "RUNNING":
                raise ValueError("Only a running job may reserve cost")
            used = con.execute("SELECT COALESCE(SUM(c.amount_idr),0) FROM costs c JOIN jobs j ON c.job_id=j.id WHERE j.video_id=? AND c.released=0", (row[2],)).fetchone()[0]
            if used + amount > min(25000, ceiling):
                raise ValueError("COST_CEILING: cumulative attempts plus reservation exceed IDR ceiling")
            con.execute("INSERT INTO costs(job_id,attempt,category,amount_idr,basis,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                        (job_id, row[0], "local_compute", amount, "RESERVED", "Conservative power estimate across bounded process deadline", now()))
            self.event(con, job_id, "COST_RESERVED", {"amount_idr": amount})

    def settle(self, job_id, elapsed, watts, tariff):
        estimate = elapsed / 3600 * watts / 1000 * tariff
        with self.connect() as con:
            attempt = con.execute("SELECT attempts FROM jobs WHERE id=?", (job_id,)).fetchone()[0]
            con.execute("UPDATE costs SET released=1 WHERE job_id=? AND attempt=? AND basis='RESERVED'", (job_id, attempt))
            for category, amount, basis, detail in [
                ("local_compute", estimate, "ESTIMATE", f"{elapsed:.3f}s × {watts}W × IDR{tariff}/kWh; not metered; excludes labour/depreciation"),
                ("paid_api", 0.0, "KNOWN_ACTUAL", "No paid API provider is used by the local worker"),
            ]:
                con.execute("INSERT INTO costs(job_id,attempt,category,amount_idr,basis,detail,created_at) VALUES(?,?,?,?,?,?,?)",
                            (job_id, attempt, category, amount, basis, detail, now()))
            self.event(con, job_id, "COST_SETTLED", {"estimated_local_idr": estimate, "known_paid_api_idr": 0})

    def finish(self, job_id, status, output=None, qa=None, error=None):
        if status not in {"DESIGN_REVIEW", "BLOCKED", "FAILED"}:
            raise ValueError("Workers cannot approve or publish their own work")
        with self.connect() as con:
            row = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row[0] != "RUNNING":
                raise ValueError("Job is not running")
            sha = file_hash(output) if output else None
            con.execute("UPDATE jobs SET status=?,finished_at=?,output_path=?,output_sha256=?,qa_json=?,error=? WHERE id=?",
                        (status, now(), str(output) if output else None, sha, canonical(qa) if qa else None, error, job_id))
            self.event(con, job_id, status, {"output_sha256": sha, "error": error})

    def record_expense(self, job_id, amount, category, basis, source_ref):
        """Reconcile an existing cost; this never calls or pays an external provider."""
        if not math.isfinite(amount) or amount < 0 or basis not in {"ESTIMATE", "KNOWN_ACTUAL"} or not source_ref.strip():
            raise ValueError("Finite expense, evidence reference and explicit accounting basis required")
        if category not in {"manual_local_preview", "manual_external_generation"}:
            raise ValueError("Unsupported manual expense category")
        detail = canonical({"source_ref": source_ref, "scope": "reconciled cost only; no provider call or payment"})
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            job = con.execute("SELECT video_id,attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise KeyError(job_id)
            prior = con.execute("SELECT amount_idr,basis FROM costs WHERE job_id=? AND category=? AND detail=?", (job_id, category, detail)).fetchone()
            if prior:
                if prior[0] != amount or prior[1] != basis:
                    raise ValueError("Expense reference already has a different immutable amount/basis")
                return {"status": "ALREADY_RECORDED"}
            used = con.execute("SELECT COALESCE(SUM(c.amount_idr),0) FROM costs c JOIN jobs j ON c.job_id=j.id WHERE j.video_id=? AND c.released=0", (job[0],)).fetchone()[0]
            if used + amount > 25000:
                raise ValueError("COST_CEILING: expense plus cumulative costs/reservations exceeds ceiling")
            con.execute("INSERT INTO costs(job_id,attempt,category,amount_idr,basis,detail,created_at) VALUES(?,?,?,?,?,?,?)", (job_id, job[1], category, amount, basis, detail, now()))
            self.event(con, job_id, "EXPENSE_RECONCILED", {"amount_idr": amount, "basis": basis, "category": category, "source_ref": source_ref})
            return {"status": "RECORDED"}

    def retry(self, job_id):
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row or row[0] not in {"FAILED", "BLOCKED"}:
                raise ValueError("Only failed/blocked jobs can be explicitly retried")
            con.execute("UPDATE jobs SET status='QUEUED',worker_id=NULL WHERE id=?", (job_id,))
            self.event(con, job_id, "RETRY_QUEUED", {"budget_history_preserved": True})

    def register_asset(self, path, kind, provenance, canonical_asset=False):
        path = Path(path).expanduser().resolve(strict=True)
        sha = file_hash(path)
        key = ("canonical-logo-" if canonical_asset else "asset-") + sha[:20]
        if not provenance.strip():
            raise ValueError("Asset provenance is required")
        if canonical_asset and kind != "logo":
            raise ValueError("Canonical registration here is only for an owner-provided logo")
        with self.connect() as con:
            con.execute("INSERT OR IGNORE INTO assets VALUES(?,?,?,?,?,?,?)",
                        (key, sha, str(path), kind, provenance, int(canonical_asset), now()))
            self.event(con, None, "ASSET_REGISTERED", {"asset_id": key, "sha256": sha, "canonical": canonical_asset})
        return key

    def canonical_logo(self):
        with self.connect() as con:
            row = con.execute("SELECT * FROM assets WHERE kind='logo' AND canonical=1 ORDER BY created_at DESC LIMIT 1").fetchone()
        if row:
            row = dict(row)
            if not Path(row["path"]).is_file() or file_hash(row["path"]) != row["sha256"]:
                raise ValueError("Canonical logo has changed; re-register owner-confirmed file")
            return row
        return None

    def approve(self, job_id, approver, acknowledge_human=False, acknowledge_visual=False):
        job = self.job(job_id)
        if not acknowledge_human or not approver.strip():
            raise ValueError("Explicit local human approval and identity required")
        if job["data_class"] != "PRODUCTION":
            raise ValueError("Engineering fixtures cannot be approved for publication")
        if not acknowledge_visual:
            raise ValueError("Explicit human review of the final video, captions, pacing and voice is required")
        qa = json.loads(job["qa_json"] or "{}")
        if job["status"] != "DESIGN_REVIEW" or qa.get("status") != "PASS" or qa.get("brand_status") != "PASS":
            raise ValueError("Current render, source and canonical-brand gates must pass")
        if not job["output_path"] or file_hash(job["output_path"]) != job["output_sha256"]:
            raise ValueError("Artifact changed since QA")
        with self.connect() as con:
            costs = con.execute("SELECT c.* FROM costs c JOIN jobs j ON c.job_id=j.id WHERE j.video_id=? AND c.released=0", (job["video_id"],)).fetchall()
            if any(c["basis"] == "RESERVED" for c in costs) or sum(c["amount_idr"] for c in costs) > 25000:
                raise ValueError("Costs remain reserved or exceed the video ceiling")
        logo = self.canonical_logo()
        if not logo or qa.get("logo_sha256") != logo["sha256"]:
            raise ValueError("Canonical branding differs from the rendered version")
        with self.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            current = con.execute("SELECT status,version_hash,output_sha256 FROM jobs WHERE id=?", (job_id,)).fetchone()
            if current[0] != "DESIGN_REVIEW" or current[1] != job["version_hash"] or current[2] != job["output_sha256"]:
                raise ValueError("Job changed during approval")
            approval_id = "HUMAN-" + uuid.uuid4().hex
            con.execute("INSERT INTO approvals VALUES(?,?,?,?,?,?)",
                        (approval_id, job_id, approver, job["version_hash"], job["output_sha256"], now()))
            con.execute("UPDATE jobs SET status='APPROVED' WHERE id=?", (job_id,))
            self.event(con, job_id, "HUMAN_APPROVED", {"approval_id": approval_id, "approver": approver, "visual_review_acknowledged": True, "output_sha256": job["output_sha256"]})
        return approval_id

    def snapshot(self):
        with self.connect() as con:
            return {table: [dict(r) for r in con.execute(f"SELECT * FROM {table} ORDER BY rowid DESC")]
                    for table in ["jobs", "costs", "assets", "metrics", "approvals", "events"]}
