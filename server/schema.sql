PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS events (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, authorization TEXT NOT NULL,
 purpose TEXT NOT NULL CHECK(purpose='adult-consented-evaluation'),
 authorized INTEGER NOT NULL DEFAULT 1, expires REAL NOT NULL,
 revision INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS photos (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id), hash TEXT NOT NULL,
 storage_key TEXT NOT NULL, derivative_key TEXT NOT NULL, width INTEGER NOT NULL,
 height INTEGER NOT NULL, orientation INTEGER NOT NULL, format TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', namespace TEXT, created REAL NOT NULL,
 UNIQUE(event_id,hash), UNIQUE(event_id,id)
);
CREATE TABLE IF NOT EXISTS imports (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id), batch_id TEXT NOT NULL,
 ordinal INTEGER NOT NULL, photo_id TEXT, state TEXT NOT NULL, reason TEXT, created REAL NOT NULL,
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id)
);
CREATE TABLE IF NOT EXISTS participants (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id), label TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1, generation INTEGER NOT NULL DEFAULT 1,
 UNIQUE(event_id,id)
);
CREATE TABLE IF NOT EXISTS consents (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, participant_id TEXT NOT NULL,
 purpose TEXT NOT NULL CHECK(purpose='photo-retrieval'), basis TEXT NOT NULL,
 active INTEGER NOT NULL, generation INTEGER NOT NULL, expires REAL NOT NULL, created REAL NOT NULL,
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id)
);
CREATE TABLE IF NOT EXISTS enrollments (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, participant_id TEXT NOT NULL,
 consent_id TEXT NOT NULL REFERENCES consents(id), generation INTEGER NOT NULL,
 namespace TEXT NOT NULL, vector BLOB NOT NULL, reference_count INTEGER NOT NULL, created REAL NOT NULL,
 UNIQUE(event_id,participant_id),
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id)
);
CREATE TABLE IF NOT EXISTS faces (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, photo_id TEXT NOT NULL,
 ordinal INTEGER NOT NULL, namespace TEXT NOT NULL, bbox TEXT NOT NULL, quality TEXT NOT NULL,
 vector BLOB, status TEXT NOT NULL, UNIQUE(photo_id,namespace,ordinal), UNIQUE(event_id,id),
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id)
);
CREATE TABLE IF NOT EXISTS configurations (
 id TEXT PRIMARY KEY, namespace TEXT NOT NULL, payload TEXT NOT NULL, created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, photo_id TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('process','match')), idempotency_key TEXT NOT NULL UNIQUE,
 namespace TEXT NOT NULL, config_id TEXT NOT NULL REFERENCES configurations(id),
 revision INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
 lease_owner TEXT, lease_expiry REAL, heartbeat REAL, available REAL NOT NULL,
 error TEXT, created REAL NOT NULL, elapsed REAL,
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id)
);
CREATE INDEX IF NOT EXISTS jobs_ready ON jobs(status,available,created);
CREATE TABLE IF NOT EXISTS proposed_matches (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL, photo_id TEXT NOT NULL, face_id TEXT NOT NULL,
 participant_id TEXT, generation INTEGER, config_id TEXT NOT NULL REFERENCES configurations(id),
 score REAL, margin REAL, decision TEXT NOT NULL, reason TEXT NOT NULL,
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id),
 FOREIGN KEY(event_id,face_id) REFERENCES faces(event_id,id),
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id)
);
CREATE TABLE IF NOT EXISTS released_associations (
 event_id TEXT NOT NULL, participant_id TEXT NOT NULL, photo_id TEXT NOT NULL,
 generation INTEGER NOT NULL, evidence_id TEXT NOT NULL REFERENCES proposed_matches(id),
 config_id TEXT NOT NULL REFERENCES configurations(id), outcome TEXT NOT NULL DEFAULT 'automatic',
 created REAL NOT NULL, PRIMARY KEY(event_id,participant_id,photo_id),
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id),
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id)
);
CREATE TABLE IF NOT EXISTS rejections (
 event_id TEXT NOT NULL, participant_id TEXT NOT NULL, photo_id TEXT NOT NULL, created REAL NOT NULL,
 PRIMARY KEY(event_id,participant_id,photo_id),
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id),
 FOREIGN KEY(event_id,photo_id) REFERENCES photos(event_id,id)
);
CREATE TABLE IF NOT EXISTS deletions (
 id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id), participant_id TEXT,
 scope TEXT NOT NULL, created REAL NOT NULL, completed REAL, verification TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), participant_id TEXT,
 role TEXT NOT NULL CHECK(role IN ('operator','guest')), generation INTEGER, expires REAL NOT NULL,
 FOREIGN KEY(event_id,participant_id) REFERENCES participants(event_id,id)
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), config_id TEXT NOT NULL,
 synthetic INTEGER NOT NULL, metadata TEXT NOT NULL, created REAL NOT NULL
);
