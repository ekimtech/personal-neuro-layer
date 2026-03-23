# === contacts_server/server.py ===
import os
import sqlite3
from flask import Blueprint, request, jsonify, render_template

contacts_bp = Blueprint("contacts_bp", __name__)

# Unified DB path
CONTACTS_DB_PATH = os.path.join(
    "mcp_servers_hub",
    "memory_servers",
    "sqlite_server",
    "contacts.db"
)

# Ensure folder exists
os.makedirs(os.path.dirname(CONTACTS_DB_PATH), exist_ok=True)

# ---------------------------------------------------------
# DB INITIALIZER
# ---------------------------------------------------------
def init_contacts_db():
    conn = sqlite3.connect(CONTACTS_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            address TEXT,
            business_name TEXT,
            group_name TEXT
        )
    """)

    conn.commit()
    conn.close()

init_contacts_db()

# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------
def add_contact(first, last, email, phone, address, business, group):
    conn = sqlite3.connect(CONTACTS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO contacts (first_name, last_name, email, phone, address, business_name, group_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (first, last, email, phone, address, business, group))
    conn.commit()
    conn.close()

def delete_contact(contact_id):
    conn = sqlite3.connect(CONTACTS_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
    conn.commit()
    conn.close()

def search_contacts(term):
    conn = sqlite3.connect(CONTACTS_DB_PATH)
    cursor = conn.cursor()
    like = f"%{term}%"
    cursor.execute("""
        SELECT id, first_name, last_name, email, phone, address, business_name, group_name
        FROM contacts
        WHERE first_name LIKE ? OR last_name LIKE ? OR email LIKE ? OR phone LIKE ? OR address LIKE ? OR business_name LIKE ? OR group_name LIKE ?
    """, (like, like, like, like, like, like, like))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": r[0],
            "first_name": r[1],
            "last_name": r[2],
            "email": r[3],
            "phone": r[4],
            "address": r[5],
            "business_name": r[6],
            "group": r[7]
        }
        for r in rows
    ]

# ---------------------------------------------------------
# ROUTES
# ---------------------------------------------------------

@contacts_bp.route("/contacts", methods=["GET"])
def contacts_page():
    return render_template("contacts.html")

@contacts_bp.route("/add_contact", methods=["POST"])
def add_contact_route():
    data = request.form
    add_contact(
        data.get("first_name"),
        data.get("last_name"),
        data.get("email"),
        data.get("phone"),
        data.get("address"),
        data.get("business_name"),
        data.get("group")
    )
    return render_template("contacts.html", message="Contact added successfully!")

@contacts_bp.route("/delete_contact", methods=["POST"])
def delete_contact_route():
    contact_id = request.form.get("contact_id")
    delete_contact(contact_id)
    return render_template("contacts.html", message="Contact deleted successfully!")

@contacts_bp.route("/search_contacts", methods=["GET"])
def search_contacts_route():
    term = request.args.get("search_term", "")
    results = search_contacts(term)
    return render_template("contacts.html", search_results=results, search_term=term)
