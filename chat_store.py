"""SQLite chat storage, isolated by a signed browser session."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import os
from datetime import datetime, timezone, timedelta
from threading import Lock


class StorageUnavailable(RuntimeError):
    """Safe public error: never includes a URI, credentials or server details."""


class MongoChatStore:
    """Atomic turn writes in one bounded document per browser session."""
    def __init__(self, uri):
        self.uri = uri
        self.client = None
        self._collection = None
        self._lock = Lock()

    @property
    def collection(self):
        # Defer network access until a chat/storage request. An Atlas outage
        # must not prevent crop inference and the web server from starting.
        with self._lock:
            if self._collection is None:
                from pymongo import MongoClient
                import certifi
                if self.client is None:
                    self.client = MongoClient(self.uri, connect=False, tls=True,
                        tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=False,
                        tlsAllowInvalidHostnames=False, serverSelectionTimeoutMS=10000,
                        connectTimeoutMS=10000, socketTimeoutMS=10000, maxPoolSize=5)
                collection = self.client[os.environ.get('MONGODB_DATABASE','farm_ai')].chats
                collection.create_index('expires_at', expireAfterSeconds=0)
                self._collection = collection
            return self._collection

    def _run(self, operation):
        from pymongo.errors import PyMongoError
        try:
            return operation(self.collection)
        except PyMongoError as error:
            raise StorageUnavailable('MongoDB connection unavailable') from error

    def check_connection(self):
        self._run(lambda collection: self.client.admin.command('ping'))

    def history(self, owner):
        row = self._run(lambda collection: collection.find_one({'_id':owner,'expires_at':{'$gt':datetime.now(timezone.utc)}}))
        return row.get('messages',[]) if row else []

    def append_turn(self, owner, question, answer, language):
        now = datetime.now(timezone.utc)
        messages = [{'role':role,'content':content,'language':language,'created_at':now.isoformat()}
                    for role,content in [('user',question),('assistant',answer)]]
        self._run(lambda collection: collection.update_one({'_id':owner}, {'$push':{'messages':{'$each':messages,'$slice':-100}},
            '$set':{'expires_at':now+timedelta(days=30)}}, upsert=True))

    def clear(self, owner):
        self._run(lambda collection: collection.delete_one({'_id':owner}))


class ChatStore:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, language TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)')
            db.execute('CREATE INDEX IF NOT EXISTS messages_owner ON messages(owner, id)')
            db.execute("DELETE FROM messages WHERE created_at < datetime('now', '-30 days')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def check_connection(self):
        with self.connect() as db:
            db.execute('SELECT 1')

    def history(self, owner):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT role,content,language,created_at FROM (SELECT * FROM messages WHERE owner=? ORDER BY id DESC LIMIT 100) ORDER BY id', (owner,))]

    def append_turn(self, owner, question, answer, language):
        with self.connect() as db:
            db.execute("DELETE FROM messages WHERE created_at < datetime('now', '-30 days')")
            db.executemany('INSERT INTO messages(owner,role,content,language) VALUES (?,?,?,?)', [(owner, 'user', question, language), (owner, 'assistant', answer, language)])
            db.execute('DELETE FROM messages WHERE owner=? AND id NOT IN (SELECT id FROM messages WHERE owner=? ORDER BY id DESC LIMIT 100)', (owner, owner))

    def clear(self, owner):
        with self.connect() as db:
            db.execute('DELETE FROM messages WHERE owner=?', (owner,))
