"""
Database layer for AMI Recruiting Automation.

Supports two backends:
  - SQLite    (default — local pipeline, zero configuration)
  - PostgreSQL (cloud — set DATABASE_URL to use Supabase)

To enable PostgreSQL, set DATABASE_URL in one of:
  - Streamlit Cloud secrets  (for the dashboard)
  - .env file or config.yaml (for the local pipeline)
"""

import sqlite3
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path


# ─── Backend Detection ────────────────────────────────────────────────────────

_PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_PROJECT_DIR, "ami_recruiter.db")


def _resolve_database_url():
    """
    Resolve DATABASE_URL from (in priority order):
    1. Environment variable  — Streamlit Cloud secrets inject these automatically
    2. config.yaml key       — local pipeline convenience

    Also strips any accidental square brackets Supabase puts around passwords
    in their UI (e.g. postgres:[PASSWORD] → postgres:PASSWORD) and ensures
    sslmode=require is present for Supabase connections.
    """
    url = os.environ.get('DATABASE_URL', '')
    if not url:
        try:
            import yaml
            with open(os.path.join(_PROJECT_DIR, 'config.yaml'), 'r') as f:
                _cfg = yaml.safe_load(f)
            url = _cfg.get('database_url', '') or ''
        except Exception:
            pass

    if url:
        # Strip brackets Supabase shows around passwords in their UI
        # e.g.  postgres:[MyPassword]@host  →  postgres:MyPassword@host
        import re
        url = re.sub(r':(\[)([^\]]+)(\])@', r':\2@', url)

        # Ensure SSL is enabled (required by Supabase)
        if 'supabase.co' in url and 'sslmode' not in url:
            url += '?sslmode=require'

    return url


DATABASE_URL = _resolve_database_url()
USE_POSTGRES = bool(DATABASE_URL)


# ─── Connection & Cursor Helpers ──────────────────────────────────────────────

def get_connection():
    """Open and return a database connection."""
    if USE_POSTGRES:
        import psycopg2
        try:
            return psycopg2.connect(DATABASE_URL)
        except psycopg2.OperationalError as e:
            # Surface the real error (Streamlit Cloud redacts it otherwise)
            import urllib.parse
            try:
                parsed = urllib.parse.urlparse(DATABASE_URL)
                safe_url = f"{parsed.scheme}://***:***@{parsed.hostname}:{parsed.port}{parsed.path}"
            except Exception:
                safe_url = "(could not parse URL)"
            raise RuntimeError(
                f"PostgreSQL connection failed.\n"
                f"URL used (credentials hidden): {safe_url}\n"
                f"Original error: {e}\n\n"
                f"Common fixes:\n"
                f"  1. Use the Supabase Session Pooler URL (port 5432), not the direct URL\n"
                f"     Supabase → Settings → Database → Connection pooling → Session mode\n"
                f"  2. Ensure no square brackets around the password\n"
                f"  3. Ensure ?sslmode=require is appended"
            ) from e
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _cursor(conn):
    """Return a dict-friendly cursor for the active backend."""
    if USE_POSTGRES:
        import psycopg2.extras
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return conn.cursor()


def _sql(query):
    """Translate SQLite ? placeholders → PostgreSQL %s."""
    return query.replace('?', '%s') if USE_POSTGRES else query


def _insert(cursor, sql, params):
    """Execute an INSERT and return the new row id."""
    if USE_POSTGRES:
        cursor.execute(_sql(sql) + ' RETURNING id', params)
        return cursor.fetchone()['id']
    cursor.execute(sql, params)
    return cursor.lastrowid


def _fetchone(cursor):
    """Fetch one row as a plain dict, or None."""
    row = cursor.fetchone()
    return dict(row) if row else None


def _fetchall(cursor):
    """Fetch all rows as a list of plain dicts."""
    return [dict(r) for r in cursor.fetchall()]


# ─── Schema DDL ───────────────────────────────────────────────────────────────

_SQLITE_TABLES = [
    """CREATE TABLE IF NOT EXISTS candidates (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        linkedin_url    TEXT,
        resume_filename TEXT NOT NULL,
        resume_text     TEXT,
        parsed_profile  TEXT,
        total_ami_years REAL,
        role_routing    TEXT,
        status          TEXT NOT NULL DEFAULT 'processing',
        notes           TEXT,
        resume_hash     TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS functional_scores (
        id                        INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id              INTEGER NOT NULL,
        functional_area           TEXT NOT NULL,
        gate1_pass                BOOLEAN,
        gate1_reason              TEXT,
        gate2_pass                BOOLEAN,
        gate2_reason              TEXT,
        gate3_pass                BOOLEAN,
        gate3_reason              TEXT,
        gates_passed              BOOLEAN,
        dimension_scores          TEXT,
        weighted_score            REAL,
        tier                      TEXT,
        scoring_narrative         TEXT,
        manager_stretch_flag      BOOLEAN DEFAULT 0,
        manager_stretch_narrative TEXT,
        phone_screen_questions    TEXT,
        created_at                TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""",
    """CREATE TABLE IF NOT EXISTS status_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        old_status   TEXT,
        new_status   TEXT NOT NULL,
        changed_by   TEXT DEFAULT 'system',
        notes        TEXT,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""",
    """CREATE TABLE IF NOT EXISTS rubric_feedback (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id     INTEGER NOT NULL,
        functional_area  TEXT NOT NULL,
        feedback_type    TEXT NOT NULL,
        feedback_text    TEXT NOT NULL,
        resolved         BOOLEAN DEFAULT 0,
        resolution_notes TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (candidate_id) REFERENCES candidates(id)
    )""",
    """CREATE TABLE IF NOT EXISTS processing_log (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        step         TEXT NOT NULL,
        status       TEXT NOT NULL,
        message      TEXT,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""",
]

_POSTGRES_TABLES = [
    """CREATE TABLE IF NOT EXISTS candidates (
        id              SERIAL PRIMARY KEY,
        name            TEXT NOT NULL,
        email           TEXT,
        phone           TEXT,
        linkedin_url    TEXT,
        resume_filename TEXT NOT NULL,
        resume_text     TEXT,
        parsed_profile  TEXT,
        total_ami_years FLOAT,
        role_routing    TEXT,
        status          TEXT NOT NULL DEFAULT 'processing',
        notes           TEXT,
        resume_hash     TEXT,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS functional_scores (
        id                        SERIAL PRIMARY KEY,
        candidate_id              INTEGER NOT NULL REFERENCES candidates(id),
        functional_area           TEXT NOT NULL,
        gate1_pass                BOOLEAN,
        gate1_reason              TEXT,
        gate2_pass                BOOLEAN,
        gate2_reason              TEXT,
        gate3_pass                BOOLEAN,
        gate3_reason              TEXT,
        gates_passed              BOOLEAN,
        dimension_scores          TEXT,
        weighted_score            FLOAT,
        tier                      TEXT,
        scoring_narrative         TEXT,
        manager_stretch_flag      BOOLEAN DEFAULT FALSE,
        manager_stretch_narrative TEXT,
        phone_screen_questions    TEXT,
        created_at                TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS status_history (
        id           SERIAL PRIMARY KEY,
        candidate_id INTEGER NOT NULL REFERENCES candidates(id),
        old_status   TEXT,
        new_status   TEXT NOT NULL,
        changed_by   TEXT DEFAULT 'system',
        notes        TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS rubric_feedback (
        id               SERIAL PRIMARY KEY,
        candidate_id     INTEGER NOT NULL REFERENCES candidates(id),
        functional_area  TEXT NOT NULL,
        feedback_type    TEXT NOT NULL,
        feedback_text    TEXT NOT NULL,
        resolved         BOOLEAN DEFAULT FALSE,
        resolution_notes TEXT,
        created_at       TIMESTAMPTZ DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS processing_log (
        id           SERIAL PRIMARY KEY,
        candidate_id INTEGER,
        step         TEXT NOT NULL,
        status       TEXT NOT NULL,
        message      TEXT,
        created_at   TIMESTAMPTZ DEFAULT NOW()
    )""",
]

_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status)",
    "CREATE INDEX IF NOT EXISTS idx_candidates_created_at ON candidates(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_candidates_resume_hash ON candidates(resume_hash)",
    "CREATE INDEX IF NOT EXISTS idx_functional_scores_candidate_id ON functional_scores(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_functional_scores_tier ON functional_scores(tier)",
    "CREATE INDEX IF NOT EXISTS idx_status_history_candidate_id ON status_history(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_status_history_created_at ON status_history(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_processing_log_candidate_id ON processing_log(candidate_id)",
    "CREATE INDEX IF NOT EXISTS idx_rubric_feedback_resolved ON rubric_feedback(resolved)",
]


def init_db():
    """Initialize schema and run any pending migrations."""
    conn = get_connection()
    cur = _cursor(conn)

    tables = _POSTGRES_TABLES if USE_POSTGRES else _SQLITE_TABLES
    for stmt in tables + _INDEXES:
        cur.execute(stmt)

    # Migration: add resume_hash if missing (handles upgrade from older schema)
    if USE_POSTGRES:
        cur.execute("ALTER TABLE candidates ADD COLUMN IF NOT EXISTS resume_hash TEXT")
    else:
        try:
            cur.execute("ALTER TABLE candidates ADD COLUMN resume_hash TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()

    # Backfill hashes for existing records
    cur.execute(_sql(
        "SELECT id, resume_text FROM candidates WHERE resume_hash IS NULL AND resume_text IS NOT NULL"
    ))
    for row in _fetchall(cur):
        text = row.get('resume_text', '')
        if text and len(text) > 100:
            h = hashlib.sha256(text[:2000].encode()).hexdigest()
            cur.execute(_sql("UPDATE candidates SET resume_hash = ? WHERE id = ?"), (h, row['id']))

    conn.commit()
    conn.close()


def compute_resume_hash(resume_text):
    """Compute SHA-256 hash of resume content for duplicate detection."""
    if resume_text and len(resume_text.strip()) > 100:
        return hashlib.sha256(resume_text[:2000].encode()).hexdigest()
    return None


# ─── Candidate Operations ─────────────────────────────────────────────────────

def create_candidate(name, resume_filename, resume_text, email=None, phone=None, linkedin_url=None):
    """Create a new candidate record and return its id."""
    conn = get_connection()
    cur = _cursor(conn)
    resume_hash = compute_resume_hash(resume_text)
    candidate_id = _insert(cur,
        """INSERT INTO candidates
           (name, email, phone, linkedin_url, resume_filename, resume_text, resume_hash, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'processing')""",
        (name, email, phone, linkedin_url, resume_filename, resume_text, resume_hash)
    )
    add_status_history(candidate_id, None, 'processing', 'system',
                       'Resume received and processing started', conn)
    conn.commit()
    conn.close()
    return candidate_id


def update_candidate(candidate_id, **kwargs):
    """Update one or more candidate fields."""
    conn = get_connection()
    cur = _cursor(conn)
    valid_fields = ['name', 'email', 'phone', 'linkedin_url', 'parsed_profile',
                    'total_ami_years', 'role_routing', 'status', 'notes']
    sets, values = [], []
    for key, value in kwargs.items():
        if key in valid_fields:
            if key == 'parsed_profile' and isinstance(value, dict):
                value = json.dumps(value)
            sets.append(f"{key} = ?")
            values.append(value)
    if sets:
        sets.append("updated_at = CURRENT_TIMESTAMP")
        values.append(candidate_id)
        cur.execute(_sql(f"UPDATE candidates SET {', '.join(sets)} WHERE id = ?"), values)
    conn.commit()
    conn.close()


def update_candidate_status(candidate_id, new_status, changed_by='system', notes=None):
    """Update candidate status and record the change in history."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql("SELECT status FROM candidates WHERE id = ?"), (candidate_id,))
    row = _fetchone(cur)
    old_status = row['status'] if row else None
    cur.execute(_sql(
        "UPDATE candidates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    ), (new_status, candidate_id))
    add_status_history(candidate_id, old_status, new_status, changed_by, notes, conn)
    conn.commit()
    conn.close()


def get_candidate(candidate_id):
    """Return a single candidate dict, or None."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql("SELECT * FROM candidates WHERE id = ?"), (candidate_id,))
    row = _fetchone(cur)
    conn.close()
    return row


def get_all_candidates(status_filter=None):
    """Return all candidates as a list of dicts, optionally filtered by status."""
    conn = get_connection()
    cur = _cursor(conn)
    if status_filter:
        cur.execute(_sql(
            "SELECT * FROM candidates WHERE status = ? ORDER BY created_at DESC"
        ), (status_filter,))
    else:
        cur.execute("SELECT * FROM candidates ORDER BY created_at DESC")
    rows = _fetchall(cur)
    conn.close()
    return rows


def check_duplicate(resume_filename, resume_text):
    """Return True if this resume (by filename or content hash) already exists."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql("SELECT id FROM candidates WHERE resume_filename = ?"), (resume_filename,))
    if _fetchone(cur):
        conn.close()
        return True
    content_hash = compute_resume_hash(resume_text)
    if content_hash:
        cur.execute(_sql("SELECT id FROM candidates WHERE resume_hash = ?"), (content_hash,))
        if _fetchone(cur):
            conn.close()
            return True
    conn.close()
    return False


# ─── Scoring Operations ───────────────────────────────────────────────────────

def save_functional_score(candidate_id, functional_area, gate_results, dimension_scores,
                          weighted_score, tier, scoring_narrative, manager_stretch_flag=False,
                          manager_stretch_narrative=None, phone_screen_questions=None):
    """Save scoring results for one functional area."""
    conn = get_connection()
    cur = _cursor(conn)
    _insert(cur,
        """INSERT INTO functional_scores
           (candidate_id, functional_area,
            gate1_pass, gate1_reason, gate2_pass, gate2_reason,
            gate3_pass, gate3_reason, gates_passed,
            dimension_scores, weighted_score, tier, scoring_narrative,
            manager_stretch_flag, manager_stretch_narrative, phone_screen_questions)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            candidate_id, functional_area,
            gate_results.get('gate1_pass'), gate_results.get('gate1_reason'),
            gate_results.get('gate2_pass'), gate_results.get('gate2_reason'),
            gate_results.get('gate3_pass', True), gate_results.get('gate3_reason', ''),
            gate_results.get('gates_passed'),
            json.dumps(dimension_scores) if dimension_scores else None,
            weighted_score, tier, scoring_narrative,
            manager_stretch_flag, manager_stretch_narrative,
            json.dumps(phone_screen_questions) if phone_screen_questions else None,
        )
    )
    conn.commit()
    conn.close()


def get_candidate_scores(candidate_id):
    """Return all functional area scores for a candidate."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql(
        "SELECT * FROM functional_scores WHERE candidate_id = ? ORDER BY weighted_score DESC"
    ), (candidate_id,))
    rows = _fetchall(cur)
    conn.close()
    return rows


def get_candidates_by_tier(tier):
    """Return candidates that achieved a given tier in any functional area."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql("""
        SELECT DISTINCT c.*, fs.functional_area, fs.tier, fs.weighted_score
        FROM candidates c
        JOIN functional_scores fs ON c.id = fs.candidate_id
        WHERE fs.tier = ?
        ORDER BY fs.weighted_score DESC
    """), (tier,))
    rows = _fetchall(cur)
    conn.close()
    return rows


# ─── Status History ───────────────────────────────────────────────────────────

def add_status_history(candidate_id, old_status, new_status, changed_by='system',
                       notes=None, conn=None):
    """Record a status change. Pass an open conn to share its transaction."""
    close_conn = conn is None
    if close_conn:
        conn = get_connection()
    cur = _cursor(conn)
    _insert(cur,
        """INSERT INTO status_history (candidate_id, old_status, new_status, changed_by, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (candidate_id, old_status, new_status, changed_by, notes)
    )
    if close_conn:
        conn.commit()
        conn.close()


def get_status_history(candidate_id):
    """Return status history for a candidate in chronological order."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql(
        "SELECT * FROM status_history WHERE candidate_id = ? ORDER BY created_at ASC"
    ), (candidate_id,))
    rows = _fetchall(cur)
    conn.close()
    return rows


# ─── Rubric Feedback ──────────────────────────────────────────────────────────

def save_rubric_feedback(candidate_id, functional_area, feedback_type, feedback_text):
    """Save rubric feedback for an eliminated candidate."""
    conn = get_connection()
    cur = _cursor(conn)
    _insert(cur,
        """INSERT INTO rubric_feedback
           (candidate_id, functional_area, feedback_type, feedback_text)
           VALUES (?, ?, ?, ?)""",
        (candidate_id, functional_area, feedback_type, feedback_text)
    )
    conn.commit()
    conn.close()


def get_pending_feedback():
    """Return all unresolved rubric feedback."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute("""
        SELECT rf.*, c.name as candidate_name
        FROM rubric_feedback rf
        JOIN candidates c ON rf.candidate_id = c.id
        WHERE rf.resolved = FALSE
        ORDER BY rf.created_at DESC
    """)
    rows = _fetchall(cur)
    conn.close()
    return rows


# ─── Processing Log ───────────────────────────────────────────────────────────

def log_processing(candidate_id, step, status, message=None):
    """Append a processing step to the log."""
    conn = get_connection()
    cur = _cursor(conn)
    _insert(cur,
        "INSERT INTO processing_log (candidate_id, step, status, message) VALUES (?, ?, ?, ?)",
        (candidate_id, step, status, message)
    )
    conn.commit()
    conn.close()


# ─── Dashboard Statistics ─────────────────────────────────────────────────────

def get_dashboard_stats():
    """Return summary counts for the dashboard header."""
    conn = get_connection()
    cur = _cursor(conn)

    def _count(where=''):
        sql = f"SELECT COUNT(*) as total FROM candidates{' WHERE ' + where if where else ''}"
        cur.execute(sql)
        return _fetchone(cur)['total']

    stats = {
        'total_candidates': _count(),
        'processing':       _count("status = 'processing'"),
        'high':             _count("status = 'scored_high'"),
        'medium':           _count("status = 'scored_medium'"),
        'low':              _count("status = 'scored_low'"),
        'eliminated':       _count("status IN ('eliminated_pending_review', 'eliminated_confirmed')"),
        'passed_senior':    _count("status = 'phone_screen_pass_senior'"),
        'passed_manager':   _count("status = 'phone_screen_pass_manager'"),
        'handed_off':       _count("status = 'handed_off'"),
    }
    conn.close()
    return stats


# ─── Analytics Queries ────────────────────────────────────────────────────────

def get_recent_activity(limit=10):
    """Return the most recent status changes across all candidates."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute(_sql("""
        SELECT sh.*, c.name as candidate_name
        FROM status_history sh
        JOIN candidates c ON sh.candidate_id = c.id
        ORDER BY sh.created_at DESC
        LIMIT ?
    """), (limit,))
    rows = _fetchall(cur)
    conn.close()
    return rows


def get_processing_timeline():
    """Return daily candidate counts for a timeline chart."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM candidates
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    rows = _fetchall(cur)
    conn.close()
    return rows


def get_area_distribution():
    """Return functional area / tier counts for the analytics heatmap."""
    conn = get_connection()
    cur = _cursor(conn)
    cur.execute("""
        SELECT functional_area, tier, COUNT(*) as count
        FROM functional_scores
        GROUP BY functional_area, tier
    """)
    rows = _fetchall(cur)
    conn.close()
    return rows


# ─── Initialise on import ─────────────────────────────────────────────────────
init_db()
