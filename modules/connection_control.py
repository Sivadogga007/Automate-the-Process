"""Cross-process controls scoped to one candidate attempt."""
import sqlite3
import uuid
from contextlib import contextmanager


class ProfileSkipped(Exception):
    pass


@contextmanager
def connect(path):
    db = sqlite3.connect(path, timeout=5)
    db.execute("""CREATE TABLE IF NOT EXISTS connection_control (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1),
        attempt TEXT, name TEXT, url TEXT, phase TEXT, skip INTEGER DEFAULT 0)""")
    try:
        with db:
            yield db
    finally:
        db.close()


class ConnectionControl:
    def __init__(self, path):
        self.path = path
        self.attempt = None
        with connect(path) as db:
            db.execute('DELETE FROM connection_control')

    def begin(self, name, url):
        self.attempt = uuid.uuid4().hex
        with connect(self.path) as db:
            db.execute('INSERT OR REPLACE INTO connection_control VALUES(1,?,?,?,?,0)',
                       (self.attempt, name, url, 'reading'))

    def check(self):
        with connect(self.path) as db:
            row = db.execute('SELECT skip FROM connection_control WHERE attempt=?', (self.attempt,)).fetchone()
        if row and row[0]:
            raise ProfileSkipped('Skipped by user')

    def phase(self, value):
        with connect(self.path) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT skip FROM connection_control WHERE attempt=?', (self.attempt,)).fetchone()
            if row and row[0]:
                raise ProfileSkipped('Skipped by user')
            db.execute('UPDATE connection_control SET phase=? WHERE attempt=?', (value, self.attempt))

    def finish(self):
        with connect(self.path) as db:
            db.execute('DELETE FROM connection_control WHERE attempt=?', (self.attempt,))


def current(path):
    with connect(path) as db:
        row = db.execute('SELECT attempt,name,url,phase,skip FROM connection_control').fetchone()
    return dict(zip(('attempt','name','url','phase','skip_requested'),row)) if row else None


def request_skip(path, attempt):
    with connect(path) as db:
        changed = db.execute("""UPDATE connection_control SET skip=1
            WHERE attempt=? AND phase IN ('reading','assessing')""", (attempt,)).rowcount
    return bool(changed)
