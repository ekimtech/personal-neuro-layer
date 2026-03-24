# C:\Users\mike\Documents\Jarvis4.0\mcp_servers_hub\vector_metadata_server\vector_store.py

import os
import math
import sqlite3
from typing import List, Dict

BASE_DIR = os.path.dirname(__file__)

# Metadata DB (chunks)
METADATA_DB_PATH = os.path.join(BASE_DIR, "vector_metadata.db")

# Vector DB (embeddings)
VECTOR_DB_PATH = os.path.join(BASE_DIR, "vector_store.db")

EMBED_DIM = 64  # small, fast, deterministic


# ============================================================
# INIT VECTOR STORE DB
# ============================================================

def init_vector_db():
    conn = sqlite3.connect(VECTOR_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vector_embeddings (
            chunk_id TEXT PRIMARY KEY,
            embedding TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


init_vector_db()


# ============================================================
# WORD-LEVEL EMBEDDING (HASH-BASED, POSITION-INDEPENDENT)
# Maps each word to a consistent bucket so matching words
# in query and document produce high cosine similarity.
# Version: 2
# ============================================================

EMBED_VERSION = 2  # Bump this to force a re-index on next startup

def embed_text(text: str) -> List[float]:
    vec = [0.0] * EMBED_DIM
    for word in text.lower().split():
        # Strip punctuation so "light?" == "light"
        word = ''.join(c for c in word if c.isalnum())
        if not word:
            continue
        # Stable word hash: sum of (char_value * position_within_word)
        # Same word always maps to the same bucket regardless of sentence position
        h = sum(ord(c) * (i + 1) for i, c in enumerate(word)) % EMBED_DIM
        vec[h] += 1.0

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def serialize(vec: List[float]) -> str:
    return ",".join(f"{v:.6f}" for v in vec)


def deserialize(s: str) -> List[float]:
    return [float(x) for x in s.split(",")]


# ============================================================
# INDEX A SINGLE CHUNK
# ============================================================

def index_chunk(chunk_id: str, full_content: str) -> bool:
    vec = embed_text(full_content)
    serialized = serialize(vec)

    conn = sqlite3.connect(VECTOR_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO vector_embeddings (chunk_id, embedding)
        VALUES (?, ?)
        ON CONFLICT(chunk_id) DO UPDATE SET embedding = excluded.embedding
    """, (chunk_id, serialized))

    conn.commit()
    conn.close()
    return True


# ============================================================
# INDEX ALL CHUNKS FROM METADATA DB
# ============================================================

def index_all_chunks() -> int:
    conn_meta = sqlite3.connect(METADATA_DB_PATH)
    cursor_meta = conn_meta.cursor()

    cursor_meta.execute("SELECT id, full_content FROM vector_metadata")
    rows = cursor_meta.fetchall()
    conn_meta.close()

    count = 0
    for chunk_id, full_content in rows:
        index_chunk(chunk_id, full_content)
        count += 1

    return count


# ============================================================
# COSINE SIMILARITY
# ============================================================

def cosine(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


# ============================================================
# SEMANTIC SEARCH
# ============================================================

def search_similar(query: str, top_k: int = 5) -> List[Dict]:
    q_vec = embed_text(query)

    conn_vec = sqlite3.connect(VECTOR_DB_PATH)
    cursor_vec = conn_vec.cursor()

    cursor_vec.execute("SELECT chunk_id, embedding FROM vector_embeddings")
    rows = cursor_vec.fetchall()
    conn_vec.close()

    scored = []
    for chunk_id, emb_str in rows:
        emb_vec = deserialize(emb_str)
        score = cosine(q_vec, emb_vec)
        scored.append((chunk_id, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    if not top:
        return []

    conn_meta = sqlite3.connect(METADATA_DB_PATH)
    cursor_meta = conn_meta.cursor()

    results = []
    for chunk_id, score in top:
        cursor_meta.execute("""
            SELECT filename, file_type, chunk_index, content_preview, full_content
            FROM vector_metadata
            WHERE id = ?
        """, (chunk_id,))
        row = cursor_meta.fetchone()
        if not row:
            continue

        results.append({
            "chunk_id": chunk_id,
            "score": float(score),
            "filename": row[0],
            "file_type": row[1],
            "chunk_index": row[2],
            "content_preview": row[3],
            "full_content": row[4],
        })

    conn_meta.close()
    return results


# ============================================================
# AUTO RE-INDEX ON STARTUP
# If EMBED_VERSION doesn't match what's stored, clear all
# embeddings and rebuild so results stay accurate.
# ============================================================

def _check_and_reindex():
    try:
        conn = sqlite3.connect(VECTOR_DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS embed_version (
                id INTEGER PRIMARY KEY,
                version INTEGER NOT NULL
            )
        """)
        row = conn.execute("SELECT version FROM embed_version WHERE id = 1").fetchone()
        stored_version = row[0] if row else 0
        conn.close()

        if stored_version != EMBED_VERSION:
            # Clear stale embeddings
            conn = sqlite3.connect(VECTOR_DB_PATH)
            conn.execute("DELETE FROM vector_embeddings")
            conn.execute("""
                INSERT INTO embed_version (id, version) VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET version=excluded.version
            """, (EMBED_VERSION,))
            conn.commit()
            conn.close()

            # Re-index all chunks with new embedding
            count = index_all_chunks()
            print(f"[VectorStore] Embed version upgraded to v{EMBED_VERSION}. Re-indexed {count} chunks.")
        else:
            # Ensure chunk counts match (catches orphaned embeddings)
            conn_meta = sqlite3.connect(METADATA_DB_PATH)
            meta_count = conn_meta.execute("SELECT COUNT(*) FROM vector_metadata").fetchone()[0]
            conn_meta.close()

            conn_vec = sqlite3.connect(VECTOR_DB_PATH)
            vec_count = conn_vec.execute("SELECT COUNT(*) FROM vector_embeddings").fetchone()[0]
            conn_vec.close()

            if meta_count != vec_count:
                conn_vec = sqlite3.connect(VECTOR_DB_PATH)
                conn_vec.execute("DELETE FROM vector_embeddings")
                conn_vec.commit()
                conn_vec.close()
                count = index_all_chunks()
                print(f"[VectorStore] Count mismatch fixed. Re-indexed {count} chunks.")

    except Exception as e:
        print(f"[VectorStore] Re-index check failed: {e}")


_check_and_reindex()
