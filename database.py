"""
Database models and initialization for AMI Recruiting Automation.
Uses SQLite for zero-configuration local storage.
"""

import sqlite3
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ami_recruiter.db")


def get_connection():
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            linkedin_url TEXT,
            resume_filename TEXT NOT NULL,
            resume_text TEXT,
            parsed_profile JSON,
            total_ami_years REAL,
            role_routing TEXT,
            status TEXT NOT NULL DEFAULT 'processing',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS functional_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            functional_area TEXT NOT NULL,
            gate1_pass BOOLEAN,
            gate1_reason TEXT,
            gate2_pass BOOLEAN,
            gate2_reason TEXT,
            gate3_pass BOOLEAN,
            gate3_reason TEXT,
            gates_passed BOOLEAN,
            dimension_scores JSON,
            weighted_score REAL,
            tier TEXT,
            scoring_narrative TEXT,
            manager_stretch_flag BOOLEAN DEFAULT 0,
            manager_stretch_narrative TEXT,
            phone_screen_questions JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            old_status TEXT,
            new_status TEXT NOT NULL,
            changed_by TEXT DEFAULT 'system',
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS rubric_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            functional_area TEXT NOT NULL,
            feedback_type TEXT NOT NULL,
            feedback_text TEXT NOT NULL,
            resolved BOOLEAN DEFAULT 0,
            resolution_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        );

        CREATE TABLE IF NOT EXISTS processing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER,
            step TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # --- Schema migrations (safe to re-run) ---

    # Add resume_hash column for stronger duplicate detection
    try:
        cursor.execute("ALTER TABLE candidates ADD COLUMN resume_hash TEXT")
    except sqlite3.OperationalError:
        pass  # Column already exists

    # --- Indexes for query performance ---
    cursor.executescript("""
        CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidates(status);
        CREATE INDEX IF NOT EXISTS idx_candidates_created_at ON candidates(created_at);
        CREATE INDEX IF NOT EXISTS idx_candidates_resume_hash ON candidates(resume_hash);
        CREATE INDEX IF NOT EXISTS idx_functional_scores_candidate_id ON functional_scores(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_functional_scores_tier ON functional_scores(tier);
        CREATE INDEX IF NOT EXISTS idx_status_history_candidate_id ON status_history(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_status_history_created_at ON status_history(created_at);
        CREATE INDEX IF NOT EXISTS idx_processing_log_candidate_id ON processing_log(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_rubric_feedback_resolved ON rubric_feedback(resolved);
    """)

    # Backfill resume hashes for existing records
    cursor.execute("SELECT id, resume_text FROM candidates WHERE resume_hash IS NULL AND resume_text IS NOT NULL")
    for row in cursor.fetchall():
        text = row['resume_text'] if row['resume_text'] else ''
        if len(text) > 100:
            h = hashlib.sha256(text[:2000].encode()).hexdigest()
            cursor.execute("UPDATE candidates SET resume_hash = ? WHERE id = ?", (h, row['id']))

    conn.commit()
    conn.close()


def compute_resume_hash(resume_text):
    """Compute SHA-256 hash of resume content for duplicate detection."""
    if resume_text and len(resume_text.strip()) > 100:
        return hashlib.sha256(resume_text[:2000].encode()).hexdigest()
    return None


# --- Candidate Operations ---

def create_candidate(name, resume_filename, resume_text, email=None, phone=None, linkedin_url=None):
    """Create a new candidate record."""
    conn = get_connection()
    cursor = conn.cursor()
    resume_hash = compute_resume_hash(resume_text)
    cursor.execute("""
        INSERT INTO candidates (name, email, phone, linkedin_url, resume_filename, resume_text, resume_hash, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'processing')
    """, (name, email, phone, linkedin_url, resume_filename, resume_text, resume_hash))
    candidate_id = cursor.lastrowid
    add_status_history(candidate_id, None, 'processing', 'system', 'Resume received and processing started', conn)
    conn.commit()
    conn.close()
    return candidate_id


def update_candidate(candidate_id, **kwargs):
    """Update candidate fields."""
    conn = get_connection()
    cursor = conn.cursor()
    valid_fields = ['name', 'email', 'phone', 'linkedin_url', 'parsed_profile',
                    'total_ami_years', 'role_routing', 'status', 'notes']
    updates = []
    values = []
    for key, value in kwargs.items():
        if key in valid_fields:
            if key == 'parsed_profile' and isinstance(value, dict):
                value = json.dumps(value)
            updates.append(f"{key} = ?")
            values.append(value)
    if updates:
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(candidate_id)
        cursor.execute(f"UPDATE candidates SET {', '.join(updates)} WHERE id = ?", values)
    conn.commit()
    conn.close()


def update_candidate_status(candidate_id, new_status, changed_by='system', notes=None):
    """Update candidate status with history tracking."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    old_status = row['status'] if row else None
    cursor.execute("UPDATE candidates SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                   (new_status, candidate_id))
    add_status_history(candidate_id, old_status, new_status, changed_by, notes, conn)
    conn.commit()
    conn.close()


def get_candidate(candidate_id):
    """Get a single candidate by ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_candidates(status_filter=None):
    """Get all candidates, optionally filtered by status."""
    conn = get_connection()
    cursor = conn.cursor()
    if status_filter:
        cursor.execute("SELECT * FROM candidates WHERE status = ? ORDER BY created_at DESC", (status_filter,))
    else:
        cursor.execute("SELECT * FROM candidates ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def check_duplicate(resume_filename, resume_text):
    """Check if a resume has already been processed using filename and content hash."""
    conn = get_connection()
    cursor = conn.cursor()

    # Check by exact filename
    cursor.execute("SELECT id FROM candidates WHERE resume_filename = ?", (resume_filename,))
    if cursor.fetchone():
        conn.close()
        return True

    # Check by content hash (catches renamed duplicates)
    content_hash = compute_resume_hash(resume_text)
    if content_hash:
        cursor.execute("SELECT id FROM candidates WHERE resume_hash = ?", (content_hash,))
        if cursor.fetchone():
            conn.close()
            return True

    conn.close()
    return False


# --- Scoring Operations ---

def save_functional_score(candidate_id, functional_area, gate_results, dimension_scores,
                          weighted_score, tier, scoring_narrative, manager_stretch_flag=False,
                          manager_stretch_narrative=None, phone_screen_questions=None):
    """Save scoring results for a candidate in a functional area."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO functional_scores
        (candidate_id, functional_area, gate1_pass, gate1_reason, gate2_pass, gate2_reason,
         gate3_pass, gate3_reason, gates_passed, dimension_scores, weighted_score, tier,
         scoring_narrative, manager_stretch_flag, manager_stretch_narrative, phone_screen_questions)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        candidate_id, functional_area,
        gate_results.get('gate1_pass'), gate_results.get('gate1_reason'),
        gate_results.get('gate2_pass'), gate_results.get('gate2_reason'),
        gate_results.get('gate3_pass', True), gate_results.get('gate3_reason', ''),
        gate_results.get('gates_passed'),
        json.dumps(dimension_scores) if dimension_scores else None,
        weighted_score, tier, scoring_narrative,
        manager_stretch_flag, manager_stretch_narrative,
        json.dumps(phone_screen_questions) if phone_screen_questions else None
    ))
    conn.commit()
    conn.close()


def get_candidate_scores(candidate_id):
    """Get all functional area scores for a candidate."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM functional_scores WHERE candidate_id = ? ORDER BY weighted_score DESC",
                   (candidate_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_candidates_by_tier(tier):
    """Get all candidates with a given tier in any functional area."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT c.*, fs.functional_area, fs.tier, fs.weighted_score
        FROM candidates c
        JOIN functional_scores fs ON c.id = fs.candidate_id
        WHERE fs.tier = ?
        ORDER BY fs.weighted_score DESC
    """, (tier,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Status History ---

def add_status_history(candidate_id, old_status, new_status, changed_by='system', notes=None, conn=None):
    """Add a status change record."""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO status_history (candidate_id, old_status, new_status, changed_by, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (candidate_id, old_status, new_status, changed_by, notes))
    if close_conn:
        conn.commit()
        conn.close()


def get_status_history(candidate_id):
    """Get status history for a candidate."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM status_history WHERE candidate_id = ? ORDER BY created_at ASC",
                   (candidate_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Rubric Feedback ---

def save_rubric_feedback(candidate_id, functional_area, feedback_type, feedback_text):
    """Save rubric feedback for an eliminated candidate."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO rubric_feedback (candidate_id, functional_area, feedback_type, feedback_text)
        VALUES (?, ?, ?, ?)
    """, (candidate_id, functional_area, feedback_type, feedback_text))
    conn.commit()
    conn.close()


def get_pending_feedback():
    """Get all unresolved rubric feedback."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT rf.*, c.name as candidate_name
        FROM rubric_feedback rf
        JOIN candidates c ON rf.candidate_id = c.id
        WHERE rf.resolved = 0
        ORDER BY rf.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- Processing Log ---

def log_processing(candidate_id, step, status, message=None):
    """Log a processing step."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO processing_log (candidate_id, step, status, message)
        VALUES (?, ?, ?, ?)
    """, (candidate_id, step, status, message))
    conn.commit()
    conn.close()


# --- Dashboard Statistics ---

def get_dashboard_stats():
    """Get summary statistics for the dashboard."""
    conn = get_connection()
    cursor = conn.cursor()

    stats = {}

    cursor.execute("SELECT COUNT(*) as total FROM candidates")
    stats['total_candidates'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'processing'")
    stats['processing'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'scored_high'")
    stats['high'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'scored_medium'")
    stats['medium'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'scored_low'")
    stats['low'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status IN ('eliminated_pending_review', 'eliminated_confirmed')")
    stats['eliminated'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'phone_screen_pass_senior'")
    stats['passed_senior'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'phone_screen_pass_manager'")
    stats['passed_manager'] = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE status = 'handed_off'")
    stats['handed_off'] = cursor.fetchone()['total']

    conn.close()
    return stats


# --- Analytics Queries ---

def get_recent_activity(limit=10):
    """Get recent status changes across all candidates."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sh.*, c.name as candidate_name
        FROM status_history sh
        JOIN candidates c ON sh.candidate_id = c.id
        ORDER BY sh.created_at DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_processing_timeline():
    """Get candidate processing dates for timeline chart."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM candidates
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_area_distribution():
    """Get functional area and tier distribution for analytics."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT functional_area, tier, COUNT(*) as count
        FROM functional_scores
        GROUP BY functional_area, tier
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# Initialize DB on import
init_db()
