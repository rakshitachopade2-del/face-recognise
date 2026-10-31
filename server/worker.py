from __future__ import annotations

import argparse
import json
import threading
import time

import numpy as np

from server.config import Settings
from server.matching import decide
from server.media import MediaError, decode, safe_path
from server.providers import ProviderError
from server.service import DomainError, Service, eligible, event_access, uid


class LeaseLost(RuntimeError):
    pass


class Worker:
    def __init__(self, service):
        self.s = service

    def claim(self):
        now = time.time()
        with self.s.db.connect(write=True) as db:
            db.execute("""UPDATE jobs SET status=CASE WHEN attempts>=? THEN 'terminal_failure'
                       ELSE 'retryable_failure' END,error='lease_expired',lease_owner=NULL
                       WHERE status='running' AND lease_expiry<=?""", (self.s.settings.max_attempts, now))
            # Round-robin-ish fairness: least recently serviced event first, enrollment searches first within it.
            row = db.execute("""SELECT j.* FROM jobs j JOIN events e ON e.id=j.event_id
                 WHERE j.status IN ('pending','retryable_failure') AND j.available<=? AND j.attempts<?
                 AND j.namespace=? AND j.config_id=? AND e.active_config=j.config_id AND e.authorized=1 AND e.expires>?
                 ORDER BY COALESCE((SELECT MAX(k.heartbeat) FROM jobs k WHERE k.event_id=j.event_id),0),
                 CASE j.kind WHEN 'match' THEN 0 ELSE 1 END,j.created LIMIT 1""",
                 (now, self.s.settings.max_attempts, self.s.namespace, self.s.config_id, now)).fetchone()
            if not row:
                return None
            token = uid()
            db.execute("UPDATE jobs SET status='running',attempts=attempts+1,lease_owner=?,lease_expiry=?,heartbeat=? WHERE id=?",
                       (token, now + self.s.settings.lease_seconds, now, row["id"]))
            return dict(db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone())

    def heartbeat(self, job):
        now = time.time()
        with self.s.db.connect(write=True) as db:
            return db.execute("""UPDATE jobs SET heartbeat=?,lease_expiry=? WHERE id=? AND lease_owner=?
                              AND status='running' AND lease_expiry>?""",
                              (now, now + self.s.settings.lease_seconds, job["id"], job["lease_owner"], now)).rowcount

    def assert_lease(self, db, job):
        if not db.execute("SELECT 1 FROM jobs WHERE id=? AND lease_owner=? AND status='running' AND lease_expiry>?",
                          (job["id"], job["lease_owner"], time.time())).fetchone():
            raise LeaseLost("stale_worker")

    def process(self, job):
        with self.s.db.connect() as db:
            event_access(db, job["event_id"], self.s.config_id)
            photo = db.execute("SELECT * FROM photos WHERE event_id=? AND id=?", (job["event_id"], job["photo_id"])).fetchone()
        rgb, _, _, _ = decode(safe_path(self.s.settings.data_dir, photo["derivative_key"]).read_bytes(),
                               self.s.settings.max_bytes * 8, self.s.settings.max_pixels)
        observations = self.s.provider.analyze(rgb)
        # Publication is one short transaction. An expired owner cannot leave even one face behind.
        with self.s.db.connect(write=True) as db:
            self.assert_lease(db, job)
            event = event_access(db, job["event_id"], self.s.config_id)
            for ordinal, face in enumerate(observations):
                db.execute("INSERT OR IGNORE INTO faces VALUES (?,?,?,?,?,?,?,?,?)",
                           (uid(), job["event_id"], photo["id"], ordinal, self.s.namespace,
                            json.dumps(face.bbox), json.dumps(face.quality),
                            face.vector.astype(np.float32).tobytes() if face.vector is not None else None, face.status))
            db.execute("UPDATE photos SET state='complete',namespace=? WHERE id=?", (self.s.namespace, photo["id"]))
            self.s.queue(db, job["event_id"], photo["id"], "match", event["revision"])

    def compute_matches(self, job):
        with self.s.db.connect() as db:
            event = event_access(db, job["event_id"], self.s.config_id)
            enrollments = eligible(db, job["event_id"])
            for enrollment in enrollments:
                enrollment["vector"] = np.frombuffer(enrollment["vector"], dtype=np.float32)
            faces = db.execute("SELECT * FROM faces WHERE event_id=? AND photo_id=? AND namespace=?",
                               (job["event_id"], job["photo_id"], self.s.namespace)).fetchall()
        return event["revision"], [(face["id"], decide(
            np.frombuffer(face["vector"], dtype=np.float32) if face["vector"] else None,
            face["namespace"], enrollments, self.s.op)) for face in faces]

    def publish_matches(self, job, snapshot):
        revision, decisions = snapshot
        with self.s.db.connect(write=True) as db:
            self.assert_lease(db, job)
            event = event_access(db, job["event_id"], self.s.config_id)
            if event["revision"] != revision:
                # A newer generation gets a new idempotency key; old decisions are never published.
                self.s.queue(db, job["event_id"], job["photo_id"], "match", event["revision"])
                return
            current = {e["participant_id"]: e for e in eligible(db, job["event_id"])}
            db.execute("DELETE FROM released_associations WHERE event_id=? AND photo_id=?", (job["event_id"], job["photo_id"]))
            db.execute("DELETE FROM proposed_matches WHERE event_id=? AND photo_id=?", (job["event_id"], job["photo_id"]))
            for face_id, decision in decisions:
                person = current.get(decision.candidate)
                if decision.candidate and (not person or person["generation"] != decision.generation
                                           or person["namespace"] != self.s.namespace):
                    continue
                evidence = uid()
                rejected = db.execute("SELECT 1 FROM rejections WHERE event_id=? AND participant_id=? AND photo_id=?",
                                      (job["event_id"], decision.candidate, job["photo_id"])).fetchone()
                reason = "explicit_rejection" if rejected else decision.reason
                accepted = decision.accepted and not rejected
                db.execute("INSERT INTO proposed_matches VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (evidence, job["event_id"], job["photo_id"], face_id, decision.candidate,
                            decision.generation, self.s.config_id, decision.score, decision.margin,
                            "accepted" if accepted else "abstained", reason))
                if accepted:
                    db.execute("INSERT OR IGNORE INTO released_associations VALUES (?,?,?,?,?,?,?,?)",
                               (job["event_id"], decision.candidate, job["photo_id"], decision.generation,
                                evidence, self.s.config_id, "automatic", time.time()))

    def run_once(self, heartbeat=True):
        job = self.claim()
        if not job:
            return False
        stop = threading.Event()

        def renew():
            while not stop.wait(self.s.settings.lease_seconds / 3):
                if not self.heartbeat(job):
                    return

        thread = threading.Thread(target=renew, daemon=True)
        if heartbeat:
            thread.start()
        started = time.perf_counter()
        status, error = "complete", None
        try:
            if job["kind"] == "process":
                self.process(job)
            else:
                self.publish_matches(job, self.compute_matches(job))
        except LeaseLost:
            return True
        except (MediaError, ProviderError, DomainError) as exc:
            status, error = "terminal_failure", str(exc)
        except Exception:  # noqa: BLE001 - durable worker records a sanitized failure and bounds retries
            # Exception contents may contain sensitive filesystem paths. Keep public diagnostics categorical.
            status = "terminal_failure" if job["attempts"] >= self.s.settings.max_attempts else "retryable_failure"
            error = "processing_error"
        finally:
            stop.set()
            if heartbeat:
                thread.join(timeout=1)
        with self.s.db.connect(write=True) as db:
            db.execute("""UPDATE jobs SET status=?,error=?,elapsed=?,available=?,lease_owner=NULL,lease_expiry=NULL
                       WHERE id=? AND lease_owner=? AND status='running' AND lease_expiry>?""",
                       (status, error, time.perf_counter() - started, time.time() + min(30, 2 ** job["attempts"]),
                        job["id"], job["lease_owner"], time.time()))
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--drain", action="store_true", help="Finish currently ready work and exit")
    args = parser.parse_args()
    service = Service(Settings.environment())
    worker = Worker(service)
    print(json.dumps({"worker": "local", "synthetic": service.provider.synthetic, "namespace": service.namespace}))
    last_maintenance = 0
    while True:
        if time.monotonic() - last_maintenance > 60:
            service.maintenance()
            last_maintenance = time.monotonic()
        if not worker.run_once():
            if args.drain:
                break
            time.sleep(0.5)


if __name__ == "__main__":
    main()
