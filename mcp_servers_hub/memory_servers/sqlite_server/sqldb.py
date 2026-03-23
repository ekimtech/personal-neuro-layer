import sqlite3
import os

# Base path for all .db files
DB_PATH = os.path.dirname(__file__)

def get_connection(db_name):
    """Returns a connection to the specified SQLite database."""
    path = os.path.join(DB_PATH, db_name)
    return sqlite3.connect(path)

def init_memory_db():
    """Initializes memory.db with schema if not exists."""
    conn = get_connection("memory.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            source TEXT,
            content TEXT,
            tags TEXT,
            emotion TEXT,
            reflex_hint TEXT
        );
    """)
    conn.commit()
    conn.close()

def memory_query(qstr, limit=10):
    conn = get_connection("memory.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, timestamp, source, content, tags, emotion, reflex_hint
        FROM memory
        WHERE content LIKE ?
        ORDER BY id DESC
        LIMIT ?;
    """, (f"%{qstr}%", limit))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r[0],
            "timestamp": r[1],
            "source": r[2],
            "content": r[3],
            "tags": r[4],
            "emotion": r[5],
            "reflex_hint": r[6]
        }
        for r in rows
    ]

def insert_memory_entry(entry):
    """Inserts a memory entry into memory.db."""
    conn = get_connection("memory.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO memory (timestamp, source, content, tags, emotion, reflex_hint)
        VALUES (?, ?, ?, ?, ?, ?);
    """, (
        entry.get("timestamp"),
        entry.get("source"),
        entry.get("content"),
        entry.get("tags"),
        entry.get("emotion"),
        entry.get("reflex_hint")
    ))
    conn.commit()
    conn.close()