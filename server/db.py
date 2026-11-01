import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        directory.chmod(0o700)
        self.path = directory / "metadata.db"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(Path(__file__).with_name("schema.sql").read_text())
            if "active_config" not in {row[1] for row in db.execute("PRAGMA table_info(events)")}:
                db.execute("ALTER TABLE events ADD COLUMN active_config TEXT NOT NULL DEFAULT ''")
            for table, column, default in [('events', 'authorization_kind', 'participant_consent'),
                                           ('consents', 'basis_kind', 'participant_consent'),
                                           ('enrollments', 'policy_id', ''),
                                           ('enrollments', 'reference_hashes', '[]')]:
                if column not in {row[1] for row in db.execute(f'PRAGMA table_info({table})')}:
                    db.execute(f"ALTER TABLE {table} ADD COLUMN {column} TEXT NOT NULL DEFAULT '{default}'")
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self, write=False):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA secure_delete=ON")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.commit()
        except BaseException:
            if write:
                conn.rollback()
            raise
        finally:
            conn.close()
