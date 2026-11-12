import json
import math

from .store import canonical

COUNTERS = ("reach", "plays", "saves", "shares", "completed_plays", "attributed_orders")


def ingest(store, job_id, measurement):
    store.job(job_id)
    if not measurement.get("source_ref") or not measurement.get("observed_at"):
        raise ValueError("Source/export reference and measurement time required")
    result = dict(measurement)
    for key in COUNTERS:
        value = result.get(key)
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError(f"{key} must be a nonnegative observed integer or null")
    plays, completed = result.get("plays"), result.get("completed_plays")
    if completed is not None and (plays is None or completed > plays):
        raise ValueError("Completion denominator is plays, not reach; require consistent exported definitions")
    result["completion_rate"] = completed / plays if plays and completed is not None else None
    watch, duration = result.get("average_watch_seconds"), result.get("video_seconds")
    for name, value in [("average_watch_seconds", watch), ("video_seconds", duration), ("attributed_sales_idr", result.get("attributed_sales_idr"))]:
        if value is not None and (not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0):
            raise ValueError(f"Invalid observed value: {name}")
    result["average_watch_ratio"] = watch / duration if watch is not None and duration else None
    # Replays can make average watch ratio exceed 1; do not mislabel it completion rate.
    if result.get("attributed_sales_idr") is not None and not result.get("attribution_evidence"):
        raise ValueError("Sales attribution needs order/UTM evidence; a view is not a sale")
    if result.get("retention_curve") is not None:
        for point in result["retention_curve"]:
            if not all(isinstance(point.get(k), (int, float)) and math.isfinite(point[k]) for k in ["seconds", "retained_fraction"]):
                raise ValueError("Retention curve must contain observed numeric points")
            if point["seconds"] < 0 or not 0 <= point["retained_fraction"] <= 1:
                raise ValueError("Invalid retention point")
    with store.connect() as con:
        encoded = canonical(result)
        prior = con.execute("SELECT id FROM metrics WHERE job_id=? AND observed_at=? AND source_ref=? AND document=?",
                            (job_id, result["observed_at"], result["source_ref"], encoded)).fetchone()
        if prior:
            return prior[0]
        cur = con.execute("INSERT INTO metrics(job_id,observed_at,source_ref,document) VALUES(?,?,?,?)",
                          (job_id, result["observed_at"], result["source_ref"], encoded))
        store.event(con, job_id, "METRICS_IMPORTED", {"source_ref": result["source_ref"], "scope": "creative only; no financial ledger update"})
        return cur.lastrowid
