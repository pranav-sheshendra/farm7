"""SQLite chat storage, isolated by a signed browser session."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import os
from datetime import datetime, timezone, timedelta


class MongoChatStore:
    """Atomic turn writes in one bounded document per browser session."""
    def __init__(self, uri):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, maxPoolSize=5)
        self.collection = self.client[os.environ.get('MONGODB_DATABASE','farm_ai')].chats
        self.collection.create_index('expires_at', expireAfterSeconds=0)

    def history(self, owner):
        row = self.collection.find_one({'_id':owner,'expires_at':{'$gt':datetime.now(timezone.utc)}})
        return row.get('messages',[]) if row else []

    def append_turn(self, owner, question, answer, language):
        now = datetime.now(timezone.utc)
        messages = [{'role':role,'content':content,'language':language,'created_at':now.isoformat()}
                    for role,content in [('user',question),('assistant',answer)]]
        self.collection.update_one({'_id':owner}, {'$push':{'messages':{'$each':messages,'$slice':-100}},
            '$set':{'expires_at':now+timedelta(days=30)}}, upsert=True)

    def clear(self, owner):
        self.collection.delete_one({'_id':owner})


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
