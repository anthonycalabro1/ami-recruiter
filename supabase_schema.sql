-- ============================================================
-- AMI Recruiter - Supabase Schema
-- ============================================================
-- Run this in: Supabase project → SQL Editor → New query
-- This is provided for reference only.
-- The application will also create these tables automatically
-- on first connection via init_db().
-- ============================================================

CREATE TABLE IF NOT EXISTS candidates (
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
);

CREATE TABLE IF NOT EXISTS functional_scores (
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
);

CREATE TABLE IF NOT EXISTS status_history (
    id           SERIAL PRIMARY KEY,
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    old_status   TEXT,
    new_status   TEXT NOT NULL,
    changed_by   TEXT DEFAULT 'system',
    notes        TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rubric_feedback (
    id               SERIAL PRIMARY KEY,
    candidate_id     INTEGER NOT NULL REFERENCES candidates(id),
    functional_area  TEXT NOT NULL,
    feedback_type    TEXT NOT NULL,
    feedback_text    TEXT NOT NULL,
    resolved         BOOLEAN DEFAULT FALSE,
    resolution_notes TEXT,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_log (
    id           SERIAL PRIMARY KEY,
    candidate_id INTEGER,
    step         TEXT NOT NULL,
    status       TEXT NOT NULL,
    message      TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_candidates_status         ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_created_at     ON candidates(created_at);
CREATE INDEX IF NOT EXISTS idx_candidates_resume_hash    ON candidates(resume_hash);
CREATE INDEX IF NOT EXISTS idx_func_candidate_id         ON functional_scores(candidate_id);
CREATE INDEX IF NOT EXISTS idx_func_tier                 ON functional_scores(tier);
CREATE INDEX IF NOT EXISTS idx_history_candidate_id      ON status_history(candidate_id);
CREATE INDEX IF NOT EXISTS idx_history_created_at        ON status_history(created_at);
CREATE INDEX IF NOT EXISTS idx_log_candidate_id          ON processing_log(candidate_id);
CREATE INDEX IF NOT EXISTS idx_feedback_resolved         ON rubric_feedback(resolved);
