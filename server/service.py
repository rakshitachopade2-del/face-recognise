from __future__ import annotations

import hashlib
import json
import secrets
import time
import uuid

from server.config import OperatingPoint, digest_json
from server.db import Database
from server.matching import aggregate
from server.media import MediaError, atomic_write, decode, safe_path
from server.providers import ProviderError, create_provider


def uid():
    return uuid.uuid4().hex


class DomainError(ValueError):
    def __init__(self, code, status=400):
        super().__init__(code)
        self.status = status


def event_access(db, event_id, config_id=None):
    event = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    if not event:
        raise DomainError("event_not_found", 404)
    if not event["authorized"] or event["expires"] <= time.time():
        raise DomainError("dataset_authorization_expired_or_revoked", 403)
    if config_id is not None and event["active_config"] != config_id:
        raise DomainError("event_configuration_changed_activate_current_configuration", 409)
    return event


def eligible(db, event_id, participant_id=None, policy_id=None):
    sql = """SELECT e.*, p.label FROM enrollments e
             JOIN participants p ON p.id=e.participant_id AND p.event_id=e.event_id
             JOIN consents c ON c.id=e.consent_id AND c.event_id=e.event_id AND c.participant_id=p.id
             WHERE e.event_id=? AND p.active=1 AND c.active=1 AND c.purpose='photo-retrieval'
             AND c.expires>? AND e.generation=p.generation AND c.generation=p.generation"""
    args = [event_id, time.time()]
    if participant_id:
        sql += " AND e.participant_id=?"
        args.append(participant_id)
    if policy_id:
        sql += " AND e.policy_id=?"
        args.append(policy_id)
    return [dict(row) for row in db.execute(sql, args)]


class Service:
    def __init__(self, settings, provider=None):
        self.settings = settings
        self.op = settings.operating_point()
        self.db = Database(settings.data_dir)
        self.provider = provider or create_provider(settings, self.op)
        self.namespace = self.provider.namespace
        self.config_id = digest_json({"operating_point": self.op.model_dump(), "namespace": self.namespace})
        with self.db.connect(write=True) as db:
            db.execute("INSERT OR IGNORE INTO configurations VALUES (?,?,?,?)",
                       (self.config_id, self.namespace, self.op.model_dump_json(), time.time()))
            db.execute("UPDATE events SET active_config=? WHERE active_config=''", (self.config_id,))

    def create_event(self, name, authorization, days=30, authorization_kind='participant_consent'):
        if authorization_kind not in {'participant_consent', 'published_dataset_study_use_basis'}:
            raise DomainError('unsupported_authorization_kind')
        if not authorization.strip() or not name.strip() or not 0 < days <= 30:
            raise DomainError("name_adult_dataset_authorization_and_1_to_30_days_required")
        event_id = uid()
        now = time.time()
        with self.db.connect(write=True) as db:
            db.execute("INSERT INTO events (id,name,authorization,purpose,expires,created,active_config,authorization_kind) VALUES (?,?,?,?,?,?,?,?)",
                       (event_id, name.strip(), authorization.strip(), "adult-consented-evaluation",
                        now + days * 86400, now, self.config_id, authorization_kind))
        return event_id

    def queue(self, db, event_id, photo_id, kind, revision=0, *, config_id=None, namespace=None):
        config_id = config_id or self.config_id
        namespace = namespace or self.namespace
        if kind == 'match':
            db.execute("""UPDATE jobs SET status='superseded',lease_owner=NULL,error='newer_roster_revision'
                          WHERE event_id=? AND photo_id=? AND kind='match' AND config_id=?
                          AND revision<? AND status IN ('pending','retryable_failure','running')""",
                       (event_id, photo_id, config_id, revision))
        key = f"{kind}:{photo_id}:{namespace}:{config_id}:{revision}"
        db.execute("""INSERT OR IGNORE INTO jobs
                   (id,event_id,photo_id,kind,idempotency_key,namespace,config_id,revision,available,created)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (uid(), event_id, photo_id, kind, key, namespace, config_id, revision,
                    time.time(), time.time()))

    def import_one(self, event_id, content, batch_id, ordinal):
        with self.db.connect() as db:
            event_access(db, event_id, self.config_id)
        # Decode and filesystem IO happen outside SQLite write transactions.
        photo_id, original, derivative = uid(), None, None
        try:
            rgb, normalized, fmt, orientation = decode(content, self.settings.max_bytes, self.settings.max_pixels)
            digest = hashlib.sha256(content).hexdigest()
            with self.db.connect() as db:
                old = db.execute("SELECT id FROM photos WHERE event_id=? AND hash=?", (event_id, digest)).fetchone()
            if old:
                photo_id, state = old["id"], "duplicate"
            else:
                original, derivative = f"media/{event_id}/{uid()}.original", f"media/{event_id}/{uid()}.png"
                atomic_write(self.settings.data_dir, original, content)
                atomic_write(self.settings.data_dir, derivative, normalized)
                state = "imported"
            with self.db.connect(write=True) as db:
                event_access(db, event_id, self.config_id)
                # Recheck after IO: concurrent exact imports share one canonical record.
                old = db.execute("SELECT id FROM photos WHERE event_id=? AND hash=?", (event_id, digest)).fetchone()
                if old:
                    photo_id, state = old["id"], "duplicate"
                else:
                    db.execute("""INSERT INTO photos
                               (id,event_id,hash,storage_key,derivative_key,width,height,orientation,format,created)
                               VALUES (?,?,?,?,?,?,?,?,?,?)""",
                               (photo_id, event_id, digest, original, derivative, rgb.shape[1], rgb.shape[0],
                                orientation, fmt, time.time()))
                    self.queue(db, event_id, photo_id, "process")
                db.execute("INSERT INTO imports VALUES (?,?,?,?,?,?,?,?)",
                           (uid(), event_id, batch_id, ordinal, photo_id, state, None, time.time()))
            if state == "duplicate" and original:
                for key in (original, derivative):
                    safe_path(self.settings.data_dir, key).unlink(missing_ok=True)
            return {"ordinal": ordinal, "photo_id": photo_id, "state": state}
        except (MediaError, ProviderError) as exc:
            return self.record_import_error(event_id, batch_id, ordinal, str(exc))
        except BaseException:
            if original:
                with self.db.connect() as db:
                    saved = db.execute("SELECT 1 FROM photos WHERE storage_key=?", (original,)).fetchone()
                if not saved:
                    for key in (original, derivative):
                        safe_path(self.settings.data_dir, key).unlink(missing_ok=True)
            raise

    def record_import_error(self, event_id, batch_id, ordinal, reason):
        with self.db.connect(write=True) as db:
            event_access(db, event_id, self.config_id)
            db.execute("INSERT INTO imports VALUES (?,?,?,?,?,?,?,?)",
                       (uid(), event_id, batch_id, ordinal, None, "terminal_failure", reason, time.time()))
        return {"ordinal": ordinal, "state": "terminal_failure", "reason": reason}

    def consent(self, event_id, label, basis, days=30, basis_kind='participant_consent'):
        if not label.strip() or not basis.strip() or not 0 < days <= 30:
            raise DomainError("participant_label_active_consent_and_1_to_30_days_required")
        participant, consent = uid(), uid()
        now = time.time()
        with self.db.connect(write=True) as db:
            event = event_access(db, event_id, self.config_id)
            if basis_kind != event['authorization_kind']:
                raise DomainError('authorization_basis_kind_mismatch')
            db.execute("INSERT INTO participants (id,event_id,label) VALUES (?,?,?)", (participant, event_id, label))
            db.execute("INSERT INTO consents (id,event_id,participant_id,purpose,basis,active,generation,expires,created,basis_kind) VALUES (?,?,?,?,?,?,?,?,?,?)",
                       (consent, event_id, participant, "photo-retrieval", basis, 1, 1,
                        min(event["expires"], now + days * 86400), now, basis_kind))
        return {"participant_id": participant, "consent_id": consent, "generation": 1}

    def enroll(self, event_id, participant_id, contents):
        if len(contents) != self.op.enrollment_count:
            raise DomainError(f"supply_exactly_{self.op.enrollment_count}_references")
        with self.db.connect() as db:
            event_access(db, event_id, self.config_id)
            consent = db.execute("""SELECT c.* FROM consents c JOIN participants p ON p.id=c.participant_id
                                 WHERE c.event_id=? AND p.id=? AND c.active=1 AND p.active=1
                                 AND c.generation=p.generation AND c.expires>? AND c.purpose='photo-retrieval'""",
                                 (event_id, participant_id, time.time())).fetchone()
            if not consent:
                raise DomainError("active_purpose_specific_consent_required", 403)
            generation, consent_id = consent["generation"], consent["id"]
        vectors = []
        for content in contents:
            rgb, _, _, _ = decode(content, self.settings.max_bytes, self.settings.max_pixels)
            observations = self.provider.analyze(rgb)
            if len(observations) != 1:
                raise DomainError("reference_must_contain_exactly_one_face_retry")
            if observations[0].vector is None:
                raise DomainError("reference_quality_inadequate_retry")
            vectors.append(observations[0].vector)
        template = aggregate(vectors, self.op)
        with self.db.connect(write=True) as db:
            event_access(db, event_id, self.config_id)
            valid = db.execute("""SELECT 1 FROM consents c JOIN participants p ON p.id=c.participant_id
                               WHERE c.id=? AND c.active=1 AND p.active=1 AND c.generation=?
                               AND p.generation=? AND c.expires>?""",
                               (consent_id, generation, generation, time.time())).fetchone()
            if not valid:
                raise DomainError("consent_changed_during_enrollment", 409)
            db.execute("DELETE FROM released_associations WHERE event_id=? AND participant_id=?",
                       (event_id, participant_id))
            db.execute("DELETE FROM proposed_matches WHERE event_id=? AND participant_id=?",
                       (event_id, participant_id))
            # Re-enrollment invalidates all old jobs/sessions by increasing the generation.
            generation += 1
            db.execute("UPDATE participants SET generation=? WHERE id=?", (generation, participant_id))
            db.execute("UPDATE consents SET generation=? WHERE id=?", (generation, consent_id))
            db.execute("""INSERT INTO enrollments (id,event_id,participant_id,consent_id,generation,namespace,vector,reference_count,created,policy_id,reference_hashes) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(event_id,participant_id) DO UPDATE SET id=excluded.id,
                       consent_id=excluded.consent_id,generation=excluded.generation,namespace=excluded.namespace,
                       vector=excluded.vector,reference_count=excluded.reference_count,created=excluded.created,policy_id=excluded.policy_id,reference_hashes=excluded.reference_hashes""",
                       (uid(), event_id, participant_id, consent_id, generation, self.namespace,
                        template.tobytes(), len(vectors), time.time(), self.op.enrollment_policy,
                        json.dumps([hashlib.sha256(c).hexdigest() for c in contents])))
            self.rematch_event(db, event_id)
        return {"state": "enrolled", "generation": generation, "reference_count": len(vectors)}

    def rematch_event(self, db, event_id):
        db.execute("UPDATE events SET revision=revision+1 WHERE id=?", (event_id,))
        revision = db.execute("SELECT revision FROM events WHERE id=?", (event_id,)).fetchone()[0]
        # Existing releases must be reconsidered when the distinct-identity margin changes.
        db.execute("DELETE FROM released_associations WHERE event_id=?", (event_id,))
        event = db.execute('SELECT authorized,expires,active_config FROM events WHERE id=?', (event_id,)).fetchone()
        if not event['authorized'] or event['expires'] <= time.time():
            return
        # Revocation may arrive through an older Service or cross-event maintenance.
        # Route to persisted active configuration without loading its model or changing fences.
        config = db.execute('SELECT namespace FROM configurations WHERE id=?', (event['active_config'],)).fetchone()
        for photo in db.execute("SELECT id FROM photos WHERE event_id=? AND state='complete' AND namespace=?",
                                (event_id, config['namespace'])).fetchall():
            self.queue(db, event_id, photo["id"], "match", revision,
                       config_id=event['active_config'], namespace=config['namespace'])

    def reject(self, event_id, participant_id, photo_id):
        with self.db.connect(write=True) as db:
            event_access(db, event_id, self.config_id)
            link = db.execute("SELECT 1 FROM released_associations WHERE event_id=? AND participant_id=? AND photo_id=?",
                              (event_id, participant_id, photo_id)).fetchone()
            if not link:
                old = db.execute("SELECT 1 FROM rejections WHERE event_id=? AND participant_id=? AND photo_id=?",
                                 (event_id, participant_id, photo_id)).fetchone()
                if old:
                    return
                raise DomainError("gallery_association_not_found", 404)
            db.execute("INSERT OR IGNORE INTO rejections VALUES (?,?,?,?)",
                       (event_id, participant_id, photo_id, time.time()))
            db.execute("DELETE FROM released_associations WHERE event_id=? AND participant_id=? AND photo_id=?",
                       (event_id, participant_id, photo_id))

    def withdraw(self, event_id, participant_id):
        with self.db.connect(write=True) as db:
            person = db.execute("SELECT * FROM participants WHERE event_id=? AND id=?", (event_id, participant_id)).fetchone()
            if not person:
                raise DomainError("participant_not_found", 404)
            db.execute("UPDATE participants SET active=0,generation=generation+1 WHERE id=?", (participant_id,))
            db.execute("UPDATE consents SET active=0 WHERE event_id=? AND participant_id=?", (event_id, participant_id))
            for table in ("released_associations", "proposed_matches", "enrollments", "sessions"):
                db.execute(f"DELETE FROM {table} WHERE event_id=? AND participant_id=?", (event_id, participant_id))
            db.execute("INSERT INTO deletions VALUES (?,?,?,?,?,?,?)",
                       (uid(), event_id, participant_id, "enrollment-and-links", time.time(), time.time(),
                        "template, proposals, releases and sessions deleted; no raw references retained"))
            self.rematch_event(db, event_id)
        self.checkpoint()

    def checkpoint(self):
        with self.db.connect() as db:
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    def session(self, role, event_id=None, participant_id=None):
        if role == 'guest':
            self.require_release()
        token = secrets.token_urlsafe(32)
        generation = None
        with self.db.connect(write=True) as db:
            if role == "guest":
                event_access(db, event_id, self.config_id)
                people = eligible(db, event_id, participant_id, self.op.enrollment_policy)
                if not people or people[0]["namespace"] != self.namespace:
                    raise DomainError("active_compatible_enrollment_required", 403)
                generation = people[0]["generation"]
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?)",
                       (hashlib.sha256(token.encode()).hexdigest(), event_id, participant_id,
                        role, generation, time.time() + 3600))
        return token

    def authorize(self, token, role, event_id=None, participant_id=None):
        if role == 'guest':
            self.require_release()
        with self.db.connect() as db:
            session = db.execute("SELECT * FROM sessions WHERE token_hash=? AND expires>?",
                                 (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            if not session or session["role"] != role:
                raise DomainError("simulator_session_required", 401)
            if event_id:
                event_access(db, event_id, self.config_id)
            if role == "guest":
                people = eligible(db, event_id, participant_id, self.op.enrollment_policy)
                if (session["event_id"] != event_id or session["participant_id"] != participant_id
                        or not people or session["generation"] != people[0]["generation"]
                        or people[0]["namespace"] != self.namespace):
                    raise DomainError("gallery_authorization_revoked_or_wrong_event", 403)

    def gallery(self, event_id, participant_id):
        self.require_release()
        with self.db.connect() as db:
            event_access(db, event_id, self.config_id)
            people = eligible(db, event_id, participant_id, self.op.enrollment_policy)
            if not people or people[0]["namespace"] != self.namespace:
                raise DomainError("gallery_authorization_revoked", 403)
            return [dict(row) for row in db.execute("""SELECT p.id,p.width,p.height,r.outcome
                FROM released_associations r JOIN photos p ON p.id=r.photo_id AND p.event_id=r.event_id
                WHERE r.event_id=? AND r.participant_id=? AND r.generation=? AND r.config_id=?
                AND p.namespace=? AND NOT EXISTS (SELECT 1 FROM rejections x WHERE x.event_id=r.event_id
                AND x.participant_id=r.participant_id AND x.photo_id=r.photo_id) ORDER BY p.created""",
                (event_id, participant_id, people[0]["generation"], self.config_id, self.namespace))]

    def participant_status(self, db, event_id):
        event = event_access(db, event_id)
        config = db.execute('SELECT * FROM configurations WHERE id=?', (event['active_config'],)).fetchone()
        policy = OperatingPoint.model_validate_json(config['payload'])
        compatible = {r['participant_id']: r for r in eligible(db, event_id, policy_id=policy.enrollment_policy)
                      if r['namespace'] == config['namespace']}
        result = []
        for row in db.execute('SELECT id,label,active FROM participants WHERE event_id=?', (event_id,)):
            person = dict(row)
            enrollment = db.execute('SELECT * FROM enrollments WHERE event_id=? AND participant_id=?',
                                    (event_id, row['id'])).fetchone()
            enrolled = row['id'] in compatible
            if not row['active']:
                reason = 'Participant withdrawn.'
            elif not enrollment:
                reason = 'Enrollment references required.'
            elif enrollment['policy_id'] != policy.enrollment_policy:
                reason = 'Re-enrollment required: reference policy changed.'
            elif enrollment['namespace'] != config['namespace']:
                reason = 'Re-enrollment required: image representation changed.'
            elif not enrolled:
                reason = 'Renew authorization and re-enroll: permission expired or enrollment generation changed.'
            elif event['active_config'] != self.config_id:
                reason = 'Use the active event configuration to preview this gallery.'
            elif not policy.can_release:
                reason = 'Guest release disabled for this configuration.'
            else:
                reason = None
            result.append({**person, 'enrolled': enrolled, 'gallery_ready': enrolled and reason is None,
                           'readiness_reason': reason})
        return result

    def retry(self, event_id, job_id):
        with self.db.connect(write=True) as db:
            event_access(db, event_id, self.config_id)
            job = db.execute("SELECT * FROM jobs WHERE event_id=? AND id=? AND namespace=? AND config_id=?",
                             (event_id, job_id, self.namespace, self.config_id)).fetchone()
            if not job or job["status"] not in {"retryable_failure", "terminal_failure"}:
                raise DomainError("failed_current_configuration_job_required")
            # Explicit operator retry resets a bounded attempt window; never bypasses authorization/suppression.
            db.execute("UPDATE jobs SET status='pending',attempts=0,available=?,error=NULL WHERE id=?",
                       (time.time(), job_id))

    def require_release(self):
        if not self.op.can_release:
            raise DomainError('guest_release_disabled', 403)

    def maintenance(self):
        """Enforce shorter permissions / 30-day POC expiry; retain original photos separately."""
        now = time.time()
        with self.db.connect(write=True) as db:
            for event in db.execute("SELECT id FROM events WHERE authorized=1 AND expires<=?", (now,)).fetchall():
                event_id = event["id"]
                db.execute("UPDATE events SET authorized=0,revision=revision+1 WHERE id=?", (event_id,))
                db.execute("UPDATE participants SET active=0,generation=generation+1 WHERE event_id=?", (event_id,))
                db.execute("UPDATE consents SET active=0 WHERE event_id=?", (event_id,))
                for table in ("released_associations", "proposed_matches", "faces", "enrollments", "sessions"):
                    db.execute(f"DELETE FROM {table} WHERE event_id=?", (event_id,))
                db.execute("UPDATE jobs SET status='terminal_failure',error='authorization_expired' WHERE event_id=?", (event_id,))
                db.execute("UPDATE photos SET state='expired' WHERE event_id=?", (event_id,))
                db.execute("INSERT INTO deletions VALUES (?,?,?,?,?,?,?)", (uid(), event_id, None, "event-face-data",
                           now, None, "vectors and identity links purged; media purge pending"))
        with self.db.connect() as db:
            people = db.execute("""SELECT p.event_id,p.id FROM participants p JOIN consents c ON c.participant_id=p.id
                                 WHERE p.active=1 AND c.active=1 AND c.expires<=?""", (now,)).fetchall()
        for person in people:
            self.withdraw(person['event_id'], person['id'])
        # Event tombstones fence access before deleting files. Repeated runs resume interrupted unlinks.
        with self.db.connect() as db:
            expired = db.execute("""SELECT p.event_id,p.storage_key,p.derivative_key FROM photos p
                                    JOIN events e ON e.id=p.event_id WHERE e.authorized=0""").fetchall()
        for photo in expired:
            for key in (photo["storage_key"], photo["derivative_key"]):
                safe_path(self.settings.data_dir, key).unlink(missing_ok=True)
        with self.db.connect() as db:
            expired_events = [row[0] for row in db.execute("SELECT id FROM events WHERE authorized=0")]
            referenced = {row[0] for row in db.execute("SELECT storage_key FROM photos UNION SELECT derivative_key FROM photos")}
        for event_id in expired_events:
            directory = safe_path(self.settings.data_dir, "media/" + event_id)
            if directory.exists():
                for path in directory.iterdir():
                    if path.is_file():
                        path.unlink()  # Includes files orphaned by a crash before the import transaction.
        media = self.settings.data_dir / "media"
        if media.exists():
            for path in media.rglob("*"):
                if (path.is_file() and path.stat().st_mtime < now - 3600
                        and str(path.relative_to(self.settings.data_dir)) not in referenced):
                    path.unlink()
        with self.db.connect(write=True) as db:
            db.execute("""UPDATE deletions SET completed=?,verification='vectors, links, original and normalized files purged'
                          WHERE scope='event-face-data' AND completed IS NULL""", (time.time(),))
        self.checkpoint()

    def activate_configuration(self, event_id):
        """Explicit local reindex. Threshold-only changes reuse vectors; incompatible changes reprocess."""
        with self.db.connect(write=True) as db:
            event_access(db, event_id)
            db.execute("UPDATE events SET active_config=? WHERE id=?", (self.config_id, event_id))
            db.execute("""UPDATE jobs SET status='terminal_failure',error='configuration_superseded',lease_owner=NULL
                          WHERE event_id=? AND config_id!=? AND status!='complete'""", (event_id, self.config_id))
            self.rematch_event(db, event_id)
            revision = db.execute("SELECT revision FROM events WHERE id=?", (event_id,)).fetchone()[0]
            for photo in db.execute("SELECT id FROM photos WHERE event_id=? AND (namespace IS NULL OR namespace!=?)",
                                    (event_id, self.namespace)).fetchall():
                cached = db.execute("""SELECT 1 FROM jobs WHERE photo_id=? AND namespace=?
                                      AND kind='process' AND status='complete' LIMIT 1""",
                                    (photo["id"], self.namespace)).fetchone()
                if cached:
                    db.execute("UPDATE photos SET state='complete',namespace=? WHERE id=?",
                               (self.namespace, photo["id"]))
                    self.queue(db, event_id, photo["id"], "match", revision)
                else:
                    self.queue(db, event_id, photo["id"], "process", revision)
