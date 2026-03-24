# C:\Users\mike\Documents\Jarvis4.0\mcp_servers_hub\vector_metadata_server\server.py

import os
import sqlite3
from datetime import datetime

# ============================================================
# DATABASE PATH (inside this organ's folder)
# ============================================================

BASE_DIR = os.path.dirname(__file__)  # .../mcp_servers_hub/vector_metadata_server
DB_PATH = os.path.join(BASE_DIR, "vector_metadata.db")


# ============================================================
# INITIALIZE DATABASE
# ============================================================

def init_db():
    """Create the vector_metadata.db file and schema if missing."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vector_metadata (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content_preview TEXT NOT NULL,
            full_content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );
    """)

    conn.commit()
    conn.close()


# Initialize DB on import
init_db()


# ============================================================
# INSERT CHUNK
# ============================================================

def insert_chunk(id, filename, file_type, chunk_index, content_preview, full_content):
    """Insert a new chunk row into vector_metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    timestamp = datetime.utcnow().isoformat()

    cursor.execute("""
        INSERT INTO vector_metadata (
            id, filename, file_type, chunk_index,
            content_preview, full_content, timestamp
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (id, filename, file_type, chunk_index, content_preview, full_content, timestamp))

    conn.commit()
    conn.close()
    return True


# ============================================================
# LIST CHUNKS (pagination, search, file type filter)
# ============================================================

def list_chunks(page=1, search="", file_type=""):
    """Return paginated chunk metadata for the Vector DB Manager UI."""

    ITEMS_PER_PAGE = 20
    offset = (page - 1) * ITEMS_PER_PAGE

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Build WHERE clause dynamically
    conditions = []
    params = []

    if search:
        conditions.append("(content_preview LIKE ? OR full_content LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    if file_type:
        conditions.append("file_type = ?")
        params.append(file_type)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # Count total documents
    cursor.execute(f"SELECT COUNT(*) FROM vector_metadata {where_clause}", params)
    total_documents = cursor.fetchone()[0]

    # Fetch paginated rows
    cursor.execute(f"""
        SELECT id, filename, file_type, chunk_index, content_preview, full_content
        FROM vector_metadata
        {where_clause}
        ORDER BY timestamp DESC
        LIMIT ? OFFSET ?
    """, params + [ITEMS_PER_PAGE, offset])

    rows = cursor.fetchall()

    # Fetch distinct file types
    cursor.execute("SELECT DISTINCT file_type FROM vector_metadata")
    file_types = [r[0] for r in cursor.fetchall()]

    conn.close()

    # Format rows for UI
    documents = []
    for r in rows:
        documents.append({
            "id": r[0],
            "filename": r[1],
            "file_type": r[2],
            "chunk_index": r[3],
            "content_preview": r[4],
            "full_content": r[5]
        })

    total_pages = max(1, (total_documents + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    return {
        "documents": documents,
        "total_documents": total_documents,
        "file_types": file_types,
        "page": page,
        "total_pages": total_pages
    }


# ============================================================
# DELETE CHUNK
# ============================================================

def delete_chunk(chunk_id):
    """Delete a single chunk from both metadata and vector embeddings DBs."""
    # Delete from metadata DB
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM vector_metadata WHERE id = ?", (chunk_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()

    # Also delete from vector embeddings DB to prevent orphaned embeddings
    vector_db = os.path.join(BASE_DIR, "vector_store.db")
    if os.path.exists(vector_db):
        conn_vec = sqlite3.connect(vector_db)
        conn_vec.execute("DELETE FROM vector_embeddings WHERE chunk_id = ?", (chunk_id,))
        conn_vec.commit()
        conn_vec.close()

    return deleted


# ============================================================
# CLEAR ALL METADATA
# ============================================================

def clear_all():
    """Delete all rows from vector_metadata."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM vector_metadata")
    conn.commit()
    conn.close()

    return True
