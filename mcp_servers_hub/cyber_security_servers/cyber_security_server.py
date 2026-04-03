"""
Jarvis 4.0 — Cyber Security Server
Standalone security module — connected to Flask via routes only.
No LLM involvement. All functions are self-contained.

Modules:
  - Identity Protection : Personal info storage + data broker opt-out tracker
  - Threat Intel        : CVE feeds, dependency scanning, supply chain alerts
  - System Security     : Code integrity checks, failed auth analysis
"""

import os
import re
import json
import sqlite3
import hashlib
import datetime
import requests
import subprocess
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
PRIVACY_DB    = BASE_DIR / "privacy_scanner"  / "data" / "brokers.db"
BREACH_DB     = BASE_DIR / "breach_monitor"   / "data" / "breaches.db"
THREAT_DB     = BASE_DIR / "threat_intel"     / "data" / "threats.db"
SYSTEM_DB     = BASE_DIR / "system_security"  / "data" / "integrity.db"

# Set this to your Jarvis4.0 root folder path
JARVIS_ROOT   = Path(r"C:\path\to\your\Jarvis4.0")
REQUIREMENTS  = JARVIS_ROOT / "requirements.txt"

IDENTITY_DB   = BASE_DIR / "privacy_scanner" / "data" / "identity.db"


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE INIT
# ══════════════════════════════════════════════════════════════════════════════

def init_all_databases():
    """Initialize all SQLite databases on first run."""

    # Privacy Scanner DB
    conn = sqlite3.connect(PRIVACY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brokers (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            url         TEXT NOT NULL,
            category    TEXT,
            opt_out_url TEXT,
            status      TEXT DEFAULT 'unchecked',
            last_checked TEXT,
            notes       TEXT
        )
    """)
    conn.commit()
    conn.close()

    # Identity Protection DB
    conn = sqlite3.connect(IDENTITY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS personal_info (
            id         INTEGER PRIMARY KEY,
            first_name TEXT,
            last_name  TEXT,
            city       TEXT,
            state      TEXT,
            email      TEXT,
            phone      TEXT,
            updated_on TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS broker_submissions (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            broker_name   TEXT NOT NULL,
            submitted_on  TEXT,
            confirmed_on  TEXT,
            next_due      TEXT,
            status        TEXT DEFAULT 'pending',
            notes         TEXT
        )
    """)
    conn.commit()
    conn.close()

    # Threat Intel DB
    conn = sqlite3.connect(THREAT_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cve_alerts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            cve_id       TEXT UNIQUE,
            description  TEXT,
            severity     TEXT,
            cvss_score   REAL,
            published    TEXT,
            affected     TEXT,
            dismissed    INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS supply_chain_alerts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            package     TEXT,
            ecosystem   TEXT,
            description TEXT,
            detected_on TEXT,
            dismissed   INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dependency_scan (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            package     TEXT,
            version     TEXT,
            cve_id      TEXT,
            severity    TEXT,
            scanned_on  TEXT
        )
    """)
    conn.commit()
    conn.close()

    # System Security DB
    conn = sqlite3.connect(SYSTEM_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_hashes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath    TEXT UNIQUE,
            hash_sha256 TEXT,
            last_seen   TEXT,
            status      TEXT DEFAULT 'ok'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS auth_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ip          TEXT,
            event_type  TEXT,
            timestamp   TEXT,
            details     TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS integrity_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath    TEXT,
            change_type TEXT,
            detected_on TEXT,
            resolved    INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

    return {"status": "ok", "message": "All databases initialized"}


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 1 — IDENTITY PROTECTION
# ══════════════════════════════════════════════════════════════════════════════

# Top data brokers — search URL and opt-out URL for each
# {name} {city} {state} placeholders get replaced with personal info at runtime
IDENTITY_BROKERS = [
    {
        "name":        "Spokeo",
        "search_url":  "https://www.spokeo.com/{name}",
        "optout_url":  "https://www.spokeo.com/optout",
        "notes":       "Search your name then copy profile URL to opt-out form"
    },
    {
        "name":        "WhitePages",
        "search_url":  "https://www.whitepages.com/name/{name}/{state}",
        "optout_url":  "https://www.whitepages.com/suppression-requests",
        "notes":       "Find your listing then submit suppression request"
    },
    {
        "name":        "BeenVerified",
        "search_url":  "https://www.beenverified.com/app/optout/search",
        "optout_url":  "https://www.beenverified.com/app/optout/search",
        "notes":       "Search and opt-out on same page"
    },
    {
        "name":        "TruthFinder",
        "search_url":  "https://www.truthfinder.com/opt-out/",
        "optout_url":  "https://www.truthfinder.com/opt-out/",
        "notes":       "Search and opt-out on same page"
    },
    {
        "name":        "Instant Checkmate",
        "search_url":  "https://www.instantcheckmate.com/opt-out/",
        "optout_url":  "https://www.instantcheckmate.com/opt-out/",
        "notes":       "Search and opt-out on same page"
    },
    {
        "name":        "Radaris",
        "search_url":  "https://radaris.com/p/{name}",
        "optout_url":  "https://radaris.com/control/privacy",
        "notes":       "Find record then request removal from privacy page"
    },
    {
        "name":        "FastPeopleSearch",
        "search_url":  "https://www.fastpeoplesearch.com/name/{name}_{state}",
        "optout_url":  "https://www.fastpeoplesearch.com/removal",
        "notes":       "Copy your profile URL into removal form"
    },
    {
        "name":        "Intelius",
        "search_url":  "https://www.intelius.com/results.php?ReportType=1&qf={first}&qln={last}&qs={state}",
        "optout_url":  "https://www.intelius.com/opt-out",
        "notes":       "Search then submit opt-out with profile URL"
    },
    {
        "name":        "CheckPeople",
        "search_url":  "https://checkpeople.com/opt-out",
        "optout_url":  "https://checkpeople.com/opt-out",
        "notes":       "Search and opt-out on same page"
    },
]

# Brokers confirmed to refuse voluntary removal requests — documented for FTC reporting
REFUSED_BROKERS = [
    {"name": "PeopleFinders", "reason": "Refuses removal — state privacy law excuse"},
    {"name": "MyLife",        "reason": "Refuses voluntary removal requests"},
    {"name": "ZabaSearch",    "reason": "Removal process non-functional"},
    {"name": "PeekYou",       "reason": "Removal process non-functional"},
    {"name": "411.com",       "reason": "Removal process non-functional"},
    {"name": "USPhoneBook",   "reason": "Removal process non-functional"},
]


def get_personal_info() -> dict:
    """Return stored personal info (used to build search URLs)."""
    conn = sqlite3.connect(IDENTITY_DB)
    row = conn.execute("SELECT * FROM personal_info WHERE id=1").fetchone()
    conn.close()
    if not row:
        return {}
    return {
        "first_name": row[1], "last_name": row[2],
        "city": row[3],       "state":     row[4],
        "email": row[5],      "phone":     row[6],
        "updated_on": row[7]
    }


def save_personal_info(first_name, last_name, city, state, email, phone) -> dict:
    """Save or update personal info used for broker searches."""
    now  = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(IDENTITY_DB)
    conn.execute("""
        INSERT INTO personal_info (id, first_name, last_name, city, state, email, phone, updated_on)
        VALUES (1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            city=excluded.city,
            state=excluded.state,
            email=excluded.email,
            phone=excluded.phone,
            updated_on=excluded.updated_on
    """, (first_name, last_name, city, state, email, phone, now))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Personal info saved"}


def build_broker_urls() -> list:
    """
    Return broker list with search/opt-out URLs filled in with personal info.
    Also merges in submission status from the database.
    """
    info = get_personal_info()
    if not info:
        return IDENTITY_BROKERS  # Return base list if no info saved yet

    first = info.get("first_name", "").replace(" ", "-")
    last  = info.get("last_name",  "").replace(" ", "-")
    name  = f"{first}-{last}"
    state = info.get("state", "")

    # Load submission records
    conn = sqlite3.connect(IDENTITY_DB)
    subs = {
        row[0]: {"status": row[1], "submitted_on": row[2],
                 "confirmed_on": row[3], "next_due": row[4], "notes": row[5]}
        for row in conn.execute("""
            SELECT broker_name, status, submitted_on, confirmed_on, next_due, notes
            FROM broker_submissions
        """).fetchall()
    }
    conn.close()

    result = []
    for b in IDENTITY_BROKERS:
        search_url = (b["search_url"]
            .replace("{name}",  name)
            .replace("{first}", first)
            .replace("{last}",  last)
            .replace("{state}", state))
        sub = subs.get(b["name"], {})
        result.append({
            "name":         b["name"],
            "search_url":   search_url,
            "optout_url":   b["optout_url"],
            "instructions": b["notes"],
            "status":       sub.get("status", "not_started"),
            "submitted_on": sub.get("submitted_on"),
            "confirmed_on": sub.get("confirmed_on"),
            "next_due":     sub.get("next_due"),
        })
    return result


def log_broker_submission(broker_name: str, action: str, notes: str = "") -> dict:
    """
    Log a submission or confirmation for a broker opt-out.
    action: 'submitted' | 'confirmed' | 'reset'
    """
    now      = datetime.datetime.now().isoformat()
    next_due = (datetime.datetime.now() + datetime.timedelta(days=90)).strftime("%Y-%m-%d")
    conn     = sqlite3.connect(IDENTITY_DB)

    existing = conn.execute(
        "SELECT id FROM broker_submissions WHERE broker_name=?", (broker_name,)
    ).fetchone()

    if action == "submitted":
        if existing:
            conn.execute(
                "UPDATE broker_submissions SET status='submitted', submitted_on=?, next_due=?, notes=? WHERE broker_name=?",
                (now, next_due, notes, broker_name)
            )
        else:
            conn.execute(
                "INSERT INTO broker_submissions (broker_name, status, submitted_on, next_due, notes) VALUES (?,?,?,?,?)",
                (broker_name, "submitted", now, next_due, notes)
            )

    elif action == "confirmed":
        if existing:
            conn.execute(
                "UPDATE broker_submissions SET status='confirmed', confirmed_on=?, next_due=?, notes=? WHERE broker_name=?",
                (now, next_due, notes, broker_name)
            )
        else:
            conn.execute(
                "INSERT INTO broker_submissions (broker_name, status, confirmed_on, next_due, notes) VALUES (?,?,?,?,?)",
                (broker_name, "confirmed", now, next_due, notes)
            )

    elif action == "reset":
        conn.execute("DELETE FROM broker_submissions WHERE broker_name=?", (broker_name,))

    conn.commit()
    conn.close()
    return {"status": "ok", "broker": broker_name, "action": action, "next_due": next_due}


def get_identity_summary() -> dict:
    """Summary counts for dashboard cards."""
    conn        = sqlite3.connect(IDENTITY_DB)
    total       = len(IDENTITY_BROKERS)
    confirmed   = conn.execute("SELECT COUNT(*) FROM broker_submissions WHERE status='confirmed'").fetchone()[0]
    submitted   = conn.execute("SELECT COUNT(*) FROM broker_submissions WHERE status='submitted'").fetchone()[0]
    due_soon    = conn.execute("""
        SELECT COUNT(*) FROM broker_submissions
        WHERE next_due <= date('now', '+14 days') AND status != 'not_started'
    """).fetchone()[0]
    conn.close()
    return {
        "total":       total,
        "confirmed":   confirmed,
        "submitted":   submitted,
        "not_started": total - confirmed - submitted,
        "due_soon":    due_soon
    }


def seed_brokers():
    """
    Seed the database with known data brokers.
    Source: community-maintained list (Daniel Miessler / Privacy Guides)
    Add more rows as needed.
    """
    brokers = [
        ("Spokeo",          "https://www.spokeo.com",          "people-search", "https://www.spokeo.com/optout"),
        ("WhitePages",      "https://www.whitepages.com",      "people-search", "https://www.whitepages.com/suppression-requests"),
        ("BeenVerified",    "https://www.beenverified.com",    "background",    "https://www.beenverified.com/app/optout/search"),
        ("Intelius",        "https://www.intelius.com",        "people-search", "https://www.intelius.com/opt-out"),
        ("Pipl",            "https://pipl.com",                "people-search", "https://pipl.com/personal-information-removal-request"),
        ("ZabaSearch",      "https://www.zabasearch.com",      "people-search", "https://www.zabasearch.com/optout"),
        ("PeopleFinders",   "https://www.peoplefinders.com",   "people-search", "https://www.peoplefinders.com/opt-out"),
        ("Radaris",         "https://radaris.com",             "people-search", "https://radaris.com/control/privacy"),
        ("Acxiom",          "https://www.acxiom.com",          "data-broker",   "https://www.acxiom.com/about-acxiom/privacy/us-consumer-data-opt-out/"),
        ("LexisNexis",      "https://www.lexisnexis.com",      "data-broker",   "https://optout.lexisnexis.com/"),
        ("CoreLogic",       "https://www.corelogic.com",       "data-broker",   "https://www.corelogic.com/privacy/"),
        ("DataLogix",       "https://www.datalogix.com",       "data-broker",   "https://datalogix.com/privacy/"),
        ("TowerData",       "https://www.towerdata.com",       "data-broker",   "https://www.towerdata.com/consumers/opt_out"),
        ("Epsilon",         "https://www.epsilon.com",         "data-broker",   "https://www.epsilon.com/us/privacy-policy"),
        ("Equifax",         "https://www.equifax.com",         "credit",        "https://www.equifax.com/personal/education/privacy/"),
        ("Experian",        "https://www.experian.com",        "credit",        "https://www.experian.com/privacy/opting_out_of_marketing.html"),
        ("TransUnion",      "https://www.transunion.com",      "credit",        "https://www.transunion.com/consumer-privacy"),
        ("Verisk",          "https://www.verisk.com",          "data-broker",   "https://www.verisk.com/privacy/"),
        ("Oracle Data",     "https://www.oracle.com",          "data-broker",   "https://datacloudoptout.oracle.com/"),
        ("Neustar",         "https://www.neustar.biz",         "data-broker",   "https://www.home.neustar/privacy"),
        ("TruthFinder",     "https://www.truthfinder.com",     "people-search", "https://www.truthfinder.com/opt-out/"),
        ("Instant Checkmate","https://www.instantcheckmate.com","background",   "https://www.instantcheckmate.com/opt-out/"),
        ("CheckPeople",     "https://checkpeople.com",         "people-search", "https://checkpeople.com/opt-out"),
        ("USPhoneBook",     "https://www.usphonebook.com",     "people-search", "https://www.usphonebook.com/opt-out"),
        ("FastPeopleSearch","https://www.fastpeoplesearch.com","people-search", "https://www.fastpeoplesearch.com/removal"),
        ("411.com",         "https://www.411.com",             "people-search", "https://www.411.com/privacy"),
        ("AnyWho",          "https://www.anywho.com",          "people-search", "https://www.anywho.com/optout"),
        ("Addresses.com",   "https://www.addresses.com",       "people-search", "https://www.addresses.com/optout.php"),
        ("PublicRecords.com","https://www.publicrecords.com",  "public-records","https://www.publicrecords.com/optout"),
        ("MyLife",          "https://www.mylife.com",          "people-search", "https://www.mylife.com/ccpa/index.pubview"),
    ]

    conn = sqlite3.connect(PRIVACY_DB)
    inserted = 0
    for name, url, category, opt_out_url in brokers:
        try:
            conn.execute(
                "INSERT OR IGNORE INTO brokers (name, url, category, opt_out_url) VALUES (?,?,?,?)",
                (name, url, category, opt_out_url)
            )
            inserted += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return {"status": "ok", "seeded": inserted}


def get_broker_summary():
    """Return opt-out status summary for the dashboard."""
    conn = sqlite3.connect(PRIVACY_DB)
    rows = conn.execute("""
        SELECT status, COUNT(*) as count FROM brokers GROUP BY status
    """).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM brokers").fetchone()[0]
    conn.close()

    summary = {row[0]: row[1] for row in rows}
    return {
        "total":     total,
        "opted_out": summary.get("opted_out", 0),
        "pending":   summary.get("pending", 0),
        "unchecked": summary.get("unchecked", 0),
        "failed":    summary.get("failed", 0),
    }


def get_all_brokers():
    """Return full broker list for the dashboard table."""
    conn = sqlite3.connect(PRIVACY_DB)
    rows = conn.execute("""
        SELECT id, name, url, category, opt_out_url, status, last_checked, notes
        FROM brokers ORDER BY category, name
    """).fetchall()
    conn.close()
    return [
        {
            "id": r[0], "name": r[1], "url": r[2], "category": r[3],
            "opt_out_url": r[4], "status": r[5],
            "last_checked": r[6], "notes": r[7]
        }
        for r in rows
    ]


def update_broker_status(broker_id: int, status: str, notes: str = ""):
    """Manually update opt-out status for a broker."""
    valid = {"opted_out", "pending", "unchecked", "failed"}
    if status not in valid:
        return {"error": f"Invalid status. Use one of: {valid}"}
    conn = sqlite3.connect(PRIVACY_DB)
    conn.execute(
        "UPDATE brokers SET status=?, last_checked=?, notes=? WHERE id=?",
        (status, datetime.datetime.now().isoformat(), notes, broker_id)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "updated": broker_id}


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 2 — BREACH MONITOR
# ══════════════════════════════════════════════════════════════════════════════

def log_breach_manually(email: str, breach_name: str, breach_date: str, data_classes: str) -> dict:
    """
    Manually log a breach discovered via haveibeenpwned.com (free manual lookup).
    Visit https://haveibeenpwned.com — check your email — log results here.
    """
    if not email or not breach_name:
        return {"error": "Email and breach name are required"}

    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(BREACH_DB)
    existing = conn.execute(
        "SELECT id FROM breaches WHERE email=? AND breach_name=?",
        (email, breach_name)
    ).fetchone()

    if existing:
        conn.close()
        return {"status": "exists", "message": f"Breach '{breach_name}' already logged for {email}"}

    conn.execute(
        "INSERT INTO breaches (email, breach_name, breach_date, data_classes, detected_on) VALUES (?,?,?,?,?)",
        (email, breach_name, breach_date, data_classes, now)
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"Breach '{breach_name}' logged for {email}"}


def get_all_breaches() -> list:
    """Return all stored breach records for dashboard display."""
    conn = sqlite3.connect(BREACH_DB)
    rows = conn.execute("""
        SELECT id, email, breach_name, breach_date, data_classes, detected_on, dismissed
        FROM breaches ORDER BY detected_on DESC
    """).fetchall()
    conn.close()
    return [
        {
            "id": r[0], "email": r[1], "breach_name": r[2],
            "breach_date": r[3], "data_classes": r[4],
            "detected_on": r[5], "dismissed": r[6]
        }
        for r in rows
    ]


def dismiss_breach(breach_id: int) -> dict:
    """Mark a breach as reviewed/dismissed."""
    conn = sqlite3.connect(BREACH_DB)
    conn.execute("UPDATE breaches SET dismissed=1 WHERE id=?", (breach_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "dismissed": breach_id}


def get_breach_summary() -> dict:
    """Summary counts for dashboard."""
    conn = sqlite3.connect(BREACH_DB)
    total      = conn.execute("SELECT COUNT(*) FROM breaches").fetchone()[0]
    active     = conn.execute("SELECT COUNT(*) FROM breaches WHERE dismissed=0").fetchone()[0]
    emails     = conn.execute("SELECT COUNT(DISTINCT email) FROM breaches").fetchone()[0]
    conn.close()
    return {"total": total, "active": active, "emails_affected": emails}


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 3 — THREAT INTELLIGENCE
# ══════════════════════════════════════════════════════════════════════════════

def fetch_cve_feed(keyword: str = "python") -> dict:
    """
    Pull recent CVEs from the NVD (National Vulnerability Database) API.
    Free, no API key required for basic queries.
    """
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    params = {
        "keywordSearch": keyword,
        "resultsPerPage": 10,
        "startIndex": 0
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return {"error": f"NVD API returned {resp.status_code}"}

        data = resp.json()
        vulnerabilities = data.get("vulnerabilities", [])
        now = datetime.datetime.now().isoformat()

        conn = sqlite3.connect(THREAT_DB)
        saved = 0
        results = []

        for item in vulnerabilities:
            cve = item.get("cve", {})
            cve_id = cve.get("id", "")
            desc = ""
            for d in cve.get("descriptions", []):
                if d.get("lang") == "en":
                    desc = d.get("value", "")
                    break

            # Get CVSS score if available
            cvss_score = None
            severity = "UNKNOWN"
            metrics = cve.get("metrics", {})
            for key in ["cvssMetricV31", "cvssMetricV30", "cvssMetricV2"]:
                if key in metrics and metrics[key]:
                    m = metrics[key][0]
                    cvss_score = m.get("cvssData", {}).get("baseScore")
                    severity   = m.get("cvssData", {}).get("baseSeverity", "UNKNOWN")
                    break

            published = cve.get("published", "")

            try:
                conn.execute(
                    "INSERT OR IGNORE INTO cve_alerts (cve_id, description, severity, cvss_score, published, affected) VALUES (?,?,?,?,?,?)",
                    (cve_id, desc, severity, cvss_score, published, keyword)
                )
                saved += 1
            except Exception:
                pass

            results.append({
                "cve_id":    cve_id,
                "severity":  severity,
                "score":     cvss_score,
                "published": published,
                "summary":   desc[:200] + "..." if len(desc) > 200 else desc
            })

        conn.commit()
        conn.close()
        return {"keyword": keyword, "found": len(results), "saved": saved, "cves": results}

    except requests.exceptions.Timeout:
        return {"error": "NVD API timed out — try again in a moment"}
    except Exception as e:
        return {"error": str(e)}


def scan_dependencies() -> dict:
    """
    Scan requirements.txt against OSV (Open Source Vulnerability) database.
    Free API, no key required.
    """
    if not REQUIREMENTS.exists():
        return {"error": f"requirements.txt not found at {REQUIREMENTS}"}

    packages = []
    with open(REQUIREMENTS) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Parse name==version or name>=version etc
                match = re.match(r"([A-Za-z0-9_\-\.]+)[>=<!]=?([^\s,;]+)?", line)
                if match:
                    packages.append({
                        "name":    match.group(1),
                        "version": match.group(2) or "unknown"
                    })

    if not packages:
        return {"error": "No packages found in requirements.txt"}

    url = "https://api.osv.dev/v1/querybatch"
    queries = []
    for p in packages:
        q = {"package": {"name": p["name"], "ecosystem": "PyPI"}}
        if p["version"] != "unknown":
            q["version"] = p["version"]
        queries.append(q)

    try:
        resp = requests.post(url, json={"queries": queries}, timeout=20)
        if resp.status_code != 200:
            return {"error": f"OSV API returned {resp.status_code}"}

        results_raw = resp.json().get("results", [])
        now = datetime.datetime.now().isoformat()
        conn = sqlite3.connect(THREAT_DB)
        conn.execute("DELETE FROM dependency_scan")  # Clear old results before each scan
        vulnerable = []

        for i, result in enumerate(results_raw):
            vulns = result.get("vulns", [])
            if vulns:
                pkg = packages[i]
                for v in vulns:
                    severity = "UNKNOWN"
                    if v.get("database_specific", {}).get("severity"):
                        severity = v["database_specific"]["severity"]
                    conn.execute(
                        "INSERT INTO dependency_scan (package, version, cve_id, severity, scanned_on) VALUES (?,?,?,?,?)",
                        (pkg["name"], pkg["version"], v.get("id", ""), severity, now)
                    )
                    vulnerable.append({
                        "package":  pkg["name"],
                        "version":  pkg["version"],
                        "vuln_id":  v.get("id", ""),
                        "severity": severity,
                        "summary":  v.get("summary", "")
                    })

        conn.commit()
        conn.close()

        return {
            "packages_scanned": len(packages),
            "vulnerable":       len(vulnerable),
            "issues":           vulnerable,
            "clean":            len(packages) - len(vulnerable)
        }

    except requests.exceptions.Timeout:
        return {"error": "OSV API timed out"}
    except Exception as e:
        return {"error": str(e)}


def get_dependency_results() -> list:
    """Return all vulnerable packages found by the dependency scanner."""
    conn = sqlite3.connect(THREAT_DB)
    rows = conn.execute("""
        SELECT package, version, cve_id, severity, scanned_on
        FROM dependency_scan ORDER BY scanned_on DESC
    """).fetchall()
    conn.close()
    return [
        {"package": r[0], "version": r[1], "vuln_id": r[2],
         "severity": r[3], "scanned_on": r[4]}
        for r in rows
    ]


def get_threat_summary() -> dict:
    """Summary counts for the threat intel dashboard panel."""
    conn = sqlite3.connect(THREAT_DB)
    cve_total      = conn.execute("SELECT COUNT(*) FROM cve_alerts").fetchone()[0]
    cve_critical   = conn.execute("SELECT COUNT(*) FROM cve_alerts WHERE severity IN ('CRITICAL','HIGH') AND dismissed=0").fetchone()[0]
    dep_vulns      = conn.execute("SELECT COUNT(*) FROM dependency_scan").fetchone()[0]
    supply_alerts  = conn.execute("SELECT COUNT(*) FROM supply_chain_alerts WHERE dismissed=0").fetchone()[0]
    conn.close()
    return {
        "cve_total":     cve_total,
        "cve_critical":  cve_critical,
        "dep_vulns":     dep_vulns,
        "supply_alerts": supply_alerts
    }


def get_all_cves() -> list:
    """Return active (non-dismissed) CVE alerts for dashboard table."""
    conn = sqlite3.connect(THREAT_DB)
    rows = conn.execute("""
        SELECT id, cve_id, severity, cvss_score, published, affected, description, dismissed
        FROM cve_alerts WHERE dismissed=0
        ORDER BY cvss_score DESC, published DESC
    """).fetchall()
    conn.close()
    return [
        {
            "id": r[0], "cve_id": r[1], "severity": r[2], "score": r[3],
            "published": r[4], "affected": r[5],
            "description": r[6], "dismissed": r[7]
        }
        for r in rows
    ]


def dismiss_cve(cve_id: int) -> dict:
    """Dismiss a CVE from the active list."""
    conn = sqlite3.connect(THREAT_DB)
    conn.execute("UPDATE cve_alerts SET dismissed=1 WHERE id=?", (cve_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "dismissed": cve_id}


def clear_all_cves() -> dict:
    """Dismiss all CVEs at once — useful for clearing old irrelevant results."""
    conn = sqlite3.connect(THREAT_DB)
    count = conn.execute("UPDATE cve_alerts SET dismissed=1 WHERE dismissed=0").rowcount
    conn.commit()
    conn.close()
    return {"status": "ok", "dismissed": count}


def clear_dep_results() -> dict:
    """Clear all dependency scan results from the display."""
    conn = sqlite3.connect(THREAT_DB)
    conn.execute("DELETE FROM dependency_scan")
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Dependency scan results cleared"}


def add_supply_chain_alert(package: str, ecosystem: str, description: str) -> dict:
    """Manually log a supply chain alert (e.g. axios incident)."""
    conn = sqlite3.connect(THREAT_DB)
    conn.execute(
        "INSERT INTO supply_chain_alerts (package, ecosystem, description, detected_on) VALUES (?,?,?,?)",
        (package, ecosystem, description, datetime.datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
    return {"status": "ok", "logged": package}


# ══════════════════════════════════════════════════════════════════════════════
#  MODULE 4 — SYSTEM SECURITY
# ══════════════════════════════════════════════════════════════════════════════

WATCH_EXTENSIONS = {".py", ".html", ".js", ".json", ".md", ".txt", ".cfg", ".ini"}
SKIP_DIRS = {"venv", "__pycache__", ".git", "node_modules", "data"}

def hash_file(filepath: Path) -> str:
    """Return SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def build_integrity_baseline() -> dict:
    """
    Scan all Jarvis files and store their hashes as the trusted baseline.
    Run this once after a clean install or after intentional changes.
    """
    conn = sqlite3.connect(SYSTEM_DB)
    count = 0
    now = datetime.datetime.now().isoformat()

    for root, dirs, files in os.walk(JARVIS_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix in WATCH_EXTENSIONS:
                try:
                    h = hash_file(fpath)
                    conn.execute(
                        """INSERT INTO file_hashes (filepath, hash_sha256, last_seen, status)
                           VALUES (?,?,?,?)
                           ON CONFLICT(filepath) DO UPDATE SET
                           hash_sha256=excluded.hash_sha256,
                           last_seen=excluded.last_seen,
                           status='ok'""",
                        (str(fpath), h, now, "ok")
                    )
                    count += 1
                except Exception:
                    pass

    conn.commit()
    conn.close()
    return {"status": "ok", "files_baselined": count, "timestamp": now}


def run_integrity_check() -> dict:
    """
    Compare current file hashes against the stored baseline.
    Returns list of changed, new, or missing files.
    """
    conn = sqlite3.connect(SYSTEM_DB)
    baseline = {
        row[0]: row[1]
        for row in conn.execute("SELECT filepath, hash_sha256 FROM file_hashes").fetchall()
    }

    changed  = []
    new_files = []
    now = datetime.datetime.now().isoformat()

    for root, dirs, files in os.walk(JARVIS_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix not in WATCH_EXTENSIONS:
                continue
            fpath_str = str(fpath)
            try:
                current_hash = hash_file(fpath)
                if fpath_str in baseline:
                    if current_hash != baseline[fpath_str]:
                        changed.append(fpath_str)
                        conn.execute(
                            "INSERT INTO integrity_log (filepath, change_type, detected_on) VALUES (?,?,?)",
                            (fpath_str, "modified", now)
                        )
                        conn.execute(
                            "UPDATE file_hashes SET status='changed', last_seen=? WHERE filepath=?",
                            (now, fpath_str)
                        )
                else:
                    new_files.append(fpath_str)
                    conn.execute(
                        "INSERT INTO integrity_log (filepath, change_type, detected_on) VALUES (?,?,?)",
                        (fpath_str, "new_file", now)
                    )
            except Exception:
                pass

    # Check for missing files
    missing = []
    current_paths = set()
    for root, dirs, files in os.walk(JARVIS_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            fpath = Path(root) / fname
            if fpath.suffix in WATCH_EXTENSIONS:
                current_paths.add(str(fpath))

    for known_path in baseline:
        if known_path not in current_paths:
            missing.append(known_path)
            conn.execute(
                "INSERT INTO integrity_log (filepath, change_type, detected_on) VALUES (?,?,?)",
                (known_path, "deleted", now)
            )

    conn.commit()
    conn.close()

    return {
        "checked":   len(baseline),
        "changed":   changed,
        "new_files": new_files,
        "missing":   missing,
        "clean":     len(changed) == 0 and len(missing) == 0,
        "timestamp": now
    }


def get_integrity_log() -> list:
    """Return recent integrity change log for dashboard."""
    conn = sqlite3.connect(SYSTEM_DB)
    rows = conn.execute("""
        SELECT id, filepath, change_type, detected_on, resolved
        FROM integrity_log ORDER BY detected_on DESC LIMIT 100
    """).fetchall()
    conn.close()
    return [
        {"id": r[0], "filepath": r[1], "change_type": r[2],
         "detected_on": r[3], "resolved": r[4]}
        for r in rows
    ]


def get_system_summary() -> dict:
    """Summary counts for system security dashboard panel."""
    conn = sqlite3.connect(SYSTEM_DB)
    total_files   = conn.execute("SELECT COUNT(*) FROM file_hashes").fetchone()[0]
    changed_files = conn.execute("SELECT COUNT(*) FROM file_hashes WHERE status='changed'").fetchone()[0]
    open_issues   = conn.execute("SELECT COUNT(*) FROM integrity_log WHERE resolved=0").fetchone()[0]
    conn.close()
    return {
        "files_monitored": total_files,
        "files_changed":   changed_files,
        "open_issues":     open_issues
    }


def import_auth_events() -> dict:
    """
    Pull failed auth events from the existing Jarvis security scanner.
    Reads the ban log from the login security module.
    """
    ban_log = JARVIS_ROOT / "mcp_servers_hub" / "login_security" / "ban_log.json"
    if not ban_log.exists():
        return {"status": "ok", "message": "No ban log found yet", "imported": 0}

    try:
        with open(ban_log) as f:
            bans = json.load(f)

        conn = sqlite3.connect(SYSTEM_DB)
        imported = 0
        for entry in bans:
            ip        = entry.get("ip", "unknown")
            timestamp = entry.get("timestamp", "")
            details   = json.dumps(entry)
            existing  = conn.execute(
                "SELECT id FROM auth_events WHERE ip=? AND timestamp=?", (ip, timestamp)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO auth_events (ip, event_type, timestamp, details) VALUES (?,?,?,?)",
                    (ip, "banned", timestamp, details)
                )
                imported += 1
        conn.commit()
        conn.close()
        return {"status": "ok", "imported": imported}

    except Exception as e:
        return {"error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
#  DAILY SECURITY DIGEST  (used by nightly loop later)
# ══════════════════════════════════════════════════════════════════════════════

def generate_security_digest() -> dict:
    """
    Compile a full security summary across all three modules.
    Used by the nightly loop to generate the morning report.
    """
    broker = get_broker_summary()
    threat = get_threat_summary()
    system = get_system_summary()

    alerts = []

    if threat["cve_critical"] > 0:
        alerts.append(f"THREAT: {threat['cve_critical']} critical/high CVE(s) unresolved")

    if threat["dep_vulns"] > 0:
        alerts.append(f"DEPS: {threat['dep_vulns']} vulnerable package(s) found in requirements.txt")

    if system["files_changed"] > 0:
        alerts.append(f"INTEGRITY: {system['files_changed']} file(s) changed since last baseline")

    if system["open_issues"] > 0:
        alerts.append(f"SYSTEM: {system['open_issues']} unresolved integrity issue(s)")

    if broker["unchecked"] > 0:
        alerts.append(f"PRIVACY: {broker['unchecked']} data broker(s) not yet opted out")

    return {
        "generated":   datetime.datetime.now().isoformat(),
        "alert_count": len(alerts),
        "alerts":      alerts,
        "privacy":     broker,
        "threats":     threat,
        "system":      system,
        "status":      "CLEAN" if not alerts else "ACTION REQUIRED"
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT — init on import
# ══════════════════════════════════════════════════════════════════════════════

init_all_databases()
seed_brokers()
