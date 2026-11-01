import importlib.metadata
import json
import platform
import subprocess
import time

from server.media import atomic_write
from server.service import uid


def hardware():
    result = {"platform": platform.platform(), "machine": platform.machine(), "python": platform.python_version()}
    if platform.system() == "Darwin":
        for key, command in {"cpu": ["sysctl", "-n", "machdep.cpu.brand_string"],
                             "memory_bytes": ["sysctl", "-n", "hw.memsize"]}.items():
            result[key] = subprocess.check_output(command, text=True).strip()
    return result


def report(service, event_id=None):
    with service.db.connect() as db:
        jobs = [dict(r) for r in db.execute("SELECT status,attempts,elapsed FROM jobs WHERE (? IS NULL OR event_id=?)",
                                           (event_id, event_id))]
        counts = {table: db.execute(f"SELECT COUNT(*) FROM {table} WHERE (? IS NULL OR event_id=?)",
                                   (event_id, event_id)).fetchone()[0]
                  for table in ("photos", "faces", "enrollments", "released_associations", "rejections")}
    result = {
        "schema_version": 1, "run_id": uid(), "created_unix": time.time(), "hardware": hardware(),
        "synthetic": service.provider.synthetic,
        "label": "SYNTHETIC PIPELINE TEST — NOT RECOGNITION ACCURACY" if service.provider.synthetic else "EXPERIMENTAL LOCAL RUN",
        "provider_namespace": service.namespace, "configuration": service.op.model_dump(),
        "config_id": service.config_id, "concurrency": 1,
        "dependencies": {p: importlib.metadata.version(p) for p in
                         ("fastapi", "numpy", "opencv-python-headless", "onnxruntime", "pillow", "pillow-heif")},
        "measured": {"counts": counts, "jobs": len(jobs), "retries": sum(max(0, j["attempts"] - 1) for j in jobs),
                     "superseded_jobs": sum(j["status"] == "superseded" for j in jobs),
                     "completed_jobs": sum(j["status"] == "complete" for j in jobs),
                     "recorded_attempt_elapsed_seconds": sum(j["elapsed"] or 0 for j in jobs)},
        "not_measured": ["real recognition precision/recall", "detector recall", "fairness", "liveness",
                         "N=300/1000 accuracy", "5,000/15,000 photo throughput", "ten-event peak load",
                         "queue-inclusive p95 delivery latency", "cloud/CPU/GPU comparison", "cost",
                         "operator-reviewed recognition quality", "production licensing clearance"],
        "measurement_limit": "Job elapsed values are latest-attempt times, not full run wall time or billed compute.",
        "outcomes": {"automatic": counts["released_associations"], "operator_reviewed": 0, "guest_candidate_previews": 0},
    }
    with service.db.connect(write=True) as db:
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?)", (result["run_id"], event_id, service.config_id,
                   int(service.provider.synthetic), json.dumps(result), time.time()))
    atomic_write(service.settings.data_dir, "runs/" + result["run_id"] + ".json", json.dumps(result, indent=2).encode())
    return result


def real_benchmark_summary(reports):
    if any(r["synthetic"] for r in reports):
        raise ValueError("synthetic_runs_cannot_enter_real_model_benchmark")
    return reports
