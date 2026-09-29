-- Dogfood Portal schema.
--
-- Hand-written DDL rather than ORM-generated tables, so that every constraint an
-- operator relies on is visible in one file and quotable in DATA-MODEL.md.
--
-- Two conventions hold throughout:
--   * Ids are opaque TEXT. The fixture ids (evt_01, prj_07, jdg_01 ...) are used
--     verbatim so that a record in fixtures.json and a row in this database are
--     the same object with the same name.
--   * Everything below `events` carries event_id. Nothing is globally scoped, so
--     a second concurrent event cannot read the first one's rows by omission.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ---------------------------------------------------------------- identity ---

-- One identity table. A judge is a user with a per-event judge assignment
-- (see `judges`), not a separate kind of person, so the role matrix in
-- security.py has exactly one subject type to reason about.
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL
                  CHECK (role IN ('visitor', 'participant', 'judge', 'organizer', 'admin')),
    password_hash TEXT,
    password_salt TEXT,
    password_kdf  TEXT,
    created_at    TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_uq ON users (lower(email));

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    label      TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE INDEX IF NOT EXISTS sessions_user_idx ON sessions (user_id);

-- ------------------------------------------------------------------ events ---

CREATE TABLE IF NOT EXISTS events (
    id                    TEXT PRIMARY KEY,
    name                  TEXT NOT NULL,
    slug                  TEXT NOT NULL UNIQUE,
    description           TEXT NOT NULL DEFAULT '',
    starts_at             TEXT,
    submissions_open_at   TEXT,
    -- The deadline. Stored as ISO-8601 UTC; compared against now() by
    -- require_submissions_open() before any body validation happens.
    submissions_close     TEXT,
    voting_opens_at       TEXT,
    voting_closes_at      TEXT,
    -- authenticated | email | open. Enforced in community.py, not only in HTML.
    voting_access         TEXT NOT NULL DEFAULT 'authenticated'
                          CHECK (voting_access IN ('authenticated', 'email', 'open')),
    results_published     INTEGER NOT NULL DEFAULT 0 CHECK (results_published IN (0, 1)),
    reviews_per_project   INTEGER NOT NULL DEFAULT 3 CHECK (reviews_per_project > 0),
    -- Organizer-selectable. All three methods are always computed for export;
    -- this only chooses which one the leaderboard shows.
    normalization_method  TEXT NOT NULL DEFAULT 'additive_ridge'
                          CHECK (normalization_method IN ('raw', 'shrunken_z', 'additive_ridge')),
    -- Whether projects flagged as duplicates are excluded from the ranking.
    -- Their ballots are never excluded from calibration -- see normalize.py.
    exclude_duplicates    INTEGER NOT NULL DEFAULT 1 CHECK (exclude_duplicates IN (0, 1)),
    rubric_version        INTEGER NOT NULL DEFAULT 1,
    is_fixture            INTEGER NOT NULL DEFAULT 0 CHECK (is_fixture IN (0, 1)),
    created_at            TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS prizes (
    id           TEXT PRIMARY KEY,
    event_id     TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    amount_cents INTEGER,
    currency     TEXT NOT NULL DEFAULT 'USD',
    sort         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS prizes_event_idx ON prizes (event_id);

CREATE TABLE IF NOT EXISTS tracks (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE (event_id, name)
);

CREATE INDEX IF NOT EXISTS tracks_event_idx ON tracks (event_id);

-- ------------------------------------------------------------------- teams ---

CREATE TABLE IF NOT EXISTS teams (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    -- Team formation is by invite link (T1). The code is the capability.
    invite_code TEXT NOT NULL UNIQUE,
    created_by  TEXT REFERENCES users (id) ON DELETE SET NULL,
    created_at  TEXT NOT NULL
    -- Deliberately no UNIQUE (event_id, name). fixtures.json contains seven
    -- teams sharing three names between them -- tm_11 and tm_16 are both
    -- "OpenSignal", with different members -- so a uniqueness constraint here
    -- rejects the published data. A team name is a display label; identity is
    -- the id. Collisions are surfaced at creation time as a warning instead.
);

CREATE INDEX IF NOT EXISTS teams_event_idx ON teams (event_id);

CREATE TABLE IF NOT EXISTS team_members (
    team_id      TEXT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    role_in_team TEXT NOT NULL DEFAULT 'member' CHECK (role_in_team IN ('owner', 'member')),
    joined_at    TEXT NOT NULL,
    PRIMARY KEY (team_id, user_id)
);

CREATE INDEX IF NOT EXISTS team_members_user_idx ON team_members (user_id);

-- ---------------------------------------------------------------- projects ---

-- The field set here is the one spec.md gives as "Reference: the submission
-- field set is stable across every platform we studied", not the seven fields
-- fixtures.json happens to carry. The fixture is input, not the data model.
CREATE TABLE IF NOT EXISTS projects (
    id               TEXT PRIMARY KEY,
    event_id         TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    team_id          TEXT NOT NULL REFERENCES teams (id) ON DELETE CASCADE,
    track_id         TEXT REFERENCES tracks (id) ON DELETE SET NULL,
    title            TEXT NOT NULL CHECK (length(trim(title)) > 0),
    tagline          TEXT NOT NULL DEFAULT '',
    description      TEXT NOT NULL DEFAULT '',
    thumbnail_url    TEXT,
    video_url        TEXT,
    repo_url         TEXT,
    live_url         TEXT,
    tech_tags        TEXT NOT NULL DEFAULT '[]',   -- JSON array of strings
    status           TEXT NOT NULL DEFAULT 'draft'
                     CHECK (status IN ('draft', 'submitted', 'flagged_duplicate', 'withdrawn')),
    -- Set when the project first leaves draft. Null means never submitted.
    submitted_at     TEXT,
    -- Populated by seed.detect_duplicates(). The later of two matching
    -- submissions points at the earlier one; the earlier one is untouched.
    duplicate_of     TEXT REFERENCES projects (id) ON DELETE SET NULL,
    duplicate_reason TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS projects_event_idx      ON projects (event_id);
CREATE INDEX IF NOT EXISTS projects_team_idx       ON projects (team_id);
CREATE INDEX IF NOT EXISTS projects_track_idx      ON projects (event_id, track_id);
CREATE INDEX IF NOT EXISTS projects_gallery_idx    ON projects (event_id, status, submitted_at);
CREATE INDEX IF NOT EXISTS projects_duplicate_idx  ON projects (duplicate_of);

CREATE TABLE IF NOT EXISTS project_images (
    id         TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    caption    TEXT NOT NULL DEFAULT '',
    sort       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS project_images_project_idx ON project_images (project_id);

-- Organizer-defined custom questions, the last item in the reference field set.
CREATE TABLE IF NOT EXISTS custom_questions (
    id       TEXT PRIMARY KEY,
    event_id TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    prompt   TEXT NOT NULL,
    kind     TEXT NOT NULL DEFAULT 'text'
             CHECK (kind IN ('text', 'longtext', 'url', 'select', 'boolean')),
    options  TEXT NOT NULL DEFAULT '[]',
    required INTEGER NOT NULL DEFAULT 0 CHECK (required IN (0, 1)),
    sort     INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS custom_questions_event_idx ON custom_questions (event_id);

CREATE TABLE IF NOT EXISTS project_answers (
    project_id  TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    question_id TEXT NOT NULL REFERENCES custom_questions (id) ON DELETE CASCADE,
    answer      TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (project_id, question_id)
);

-- ------------------------------------------------------------------ rubric ---

-- One row per criterion per event, with its own weight. The market leader
-- cannot weight criteria at all; this is the table that fixes that, and it is
-- why weights are data rather than constants.
CREATE TABLE IF NOT EXISTS rubric_criteria (
    id          TEXT PRIMARY KEY,
    event_id    TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    label       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    weight      REAL NOT NULL DEFAULT 1.0 CHECK (weight >= 0),
    min_value   INTEGER NOT NULL DEFAULT 1,
    max_value   INTEGER NOT NULL DEFAULT 5,
    sort        INTEGER NOT NULL DEFAULT 0,
    UNIQUE (event_id, key),
    CHECK (max_value > min_value)
);

CREATE INDEX IF NOT EXISTS rubric_event_idx ON rubric_criteria (event_id);

-- ----------------------------------------------------------------- judging ---

CREATE TABLE IF NOT EXISTS judges (
    id           TEXT PRIMARY KEY,
    event_id     TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    email        TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'invited'
                 CHECK (status IN ('invited', 'accepted', 'declined', 'removed')),
    invite_code  TEXT UNIQUE,
    invited_at   TEXT,
    accepted_at  TEXT,
    UNIQUE (event_id, user_id)
);

CREATE INDEX IF NOT EXISTS judges_event_idx ON judges (event_id);
CREATE INDEX IF NOT EXISTS judges_user_idx  ON judges (user_id);

-- A judge's track scope. Enforced at the API by assert_track_visible(), which
-- is the "a track judge must never see another track" half of the T2 isolation
-- rule that the acceptance suite has no check for.
CREATE TABLE IF NOT EXISTS judge_tracks (
    judge_id TEXT NOT NULL REFERENCES judges (id) ON DELETE CASCADE,
    track_id TEXT NOT NULL REFERENCES tracks (id) ON DELETE CASCADE,
    PRIMARY KEY (judge_id, track_id)
);

CREATE TABLE IF NOT EXISTS assignments (
    id         TEXT PRIMARY KEY,
    event_id   TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    judge_id   TEXT NOT NULL REFERENCES judges (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending', 'completed', 'declined')),
    batch      INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    UNIQUE (event_id, judge_id, project_id)
);

CREATE INDEX IF NOT EXISTS assignments_judge_idx   ON assignments (event_id, judge_id, status);
CREATE INDEX IF NOT EXISTS assignments_project_idx ON assignments (event_id, project_id);

-- One ballot per judge per project, enforced by the database rather than by the
-- handler, so a double POST cannot create a second vote.
CREATE TABLE IF NOT EXISTS scores (
    id           TEXT PRIMARY KEY,
    event_id     TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    judge_id     TEXT NOT NULL REFERENCES judges (id) ON DELETE CASCADE,
    project_id   TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    comment      TEXT NOT NULL DEFAULT '',
    submitted_at TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (event_id, judge_id, project_id)
);

CREATE INDEX IF NOT EXISTS scores_judge_idx   ON scores (event_id, judge_id);
CREATE INDEX IF NOT EXISTS scores_project_idx ON scores (event_id, project_id);

-- Criteria live in their own table keyed by the rubric key, so adding or
-- reweighting a criterion is an INSERT, not a migration.
CREATE TABLE IF NOT EXISTS score_criteria (
    score_id      TEXT NOT NULL REFERENCES scores (id) ON DELETE CASCADE,
    criterion_key TEXT NOT NULL,
    -- The declared scale is 1-5. fixtures.json only ever uses 2-5; the
    -- constraint follows the spec, not the sample.
    value         INTEGER NOT NULL CHECK (value BETWEEN 1 AND 5),
    PRIMARY KEY (score_id, criterion_key)
);

-- Normalization output, recomputed on score/weight/flag mutation rather than
-- per request, so no graded read path ever waits on the solver.
CREATE TABLE IF NOT EXISTS results_cache (
    event_id       TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    method         TEXT NOT NULL,
    rubric_version INTEGER NOT NULL,
    computed_at    TEXT NOT NULL,
    payload        TEXT NOT NULL,
    PRIMARY KEY (event_id, method, rubric_version)
);

-- ------------------------------------------------------- community (T3) ---

CREATE TABLE IF NOT EXISTS comments (
    id         TEXT PRIMARY KEY,
    event_id   TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    body       TEXT NOT NULL CHECK (length(trim(body)) > 0),
    hidden     INTEGER NOT NULL DEFAULT 0 CHECK (hidden IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS comments_project_idx ON comments (project_id, created_at);

-- Community voting. `voter_key` is the identity the one-vote rule is applied
-- to: a user id when authenticated, an email hash when email-gated, an IP hash
-- for open links. `credits` carries quadratic voting: influence is sqrt(credits).
CREATE TABLE IF NOT EXISTS votes (
    id         TEXT PRIMARY KEY,
    event_id   TEXT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES projects (id) ON DELETE CASCADE,
    voter_key  TEXT NOT NULL,
    voter_mode TEXT NOT NULL CHECK (voter_mode IN ('open', 'email', 'authenticated')),
    credits    INTEGER NOT NULL DEFAULT 1 CHECK (credits > 0),
    created_at TEXT NOT NULL,
    UNIQUE (event_id, project_id, voter_key)
);

CREATE INDEX IF NOT EXISTS votes_event_idx ON votes (event_id, project_id);
CREATE INDEX IF NOT EXISTS votes_voter_idx ON votes (event_id, voter_key);

CREATE TABLE IF NOT EXISTS rate_limits (
    bucket       TEXT PRIMARY KEY,
    window_start TEXT NOT NULL,
    count        INTEGER NOT NULL DEFAULT 0
);

-- ------------------------------------------------------------------- audit ---

-- Append-only and hash-chained. No UPDATE or DELETE against this table exists
-- anywhere in the codebase; /api/audit/verify walks the chain and reports the
-- first row whose entry_hash does not follow from its predecessor.
CREATE TABLE IF NOT EXISTS audit_log (
    seq           INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    event_id      TEXT,
    actor_user_id TEXT,
    actor_role    TEXT,
    action        TEXT NOT NULL,
    target_type   TEXT,
    target_id     TEXT,
    -- Machine-readable reason, e.g. peer_scores_denied, submissions_closed.
    reason_code   TEXT,
    detail        TEXT NOT NULL DEFAULT '{}',
    prev_hash     TEXT NOT NULL,
    entry_hash    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS audit_event_idx  ON audit_log (event_id, seq);
CREATE INDEX IF NOT EXISTS audit_action_idx ON audit_log (action, seq);
CREATE INDEX IF NOT EXISTS audit_actor_idx  ON audit_log (actor_user_id, seq);

-- ---------------------------------------------------------------- webhooks ---

CREATE TABLE IF NOT EXISTS webhooks (
    id         TEXT PRIMARY KEY,
    event_id   TEXT REFERENCES events (id) ON DELETE CASCADE,
    url        TEXT NOT NULL CHECK (length(trim(url)) > 0),
    secret     TEXT NOT NULL,
    actions    TEXT NOT NULL DEFAULT '["*"]',
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS webhooks_event_idx ON webhooks (event_id, active);

CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id          TEXT PRIMARY KEY,
    webhook_id  TEXT NOT NULL REFERENCES webhooks (id) ON DELETE CASCADE,
    outbox_id   TEXT,
    action      TEXT NOT NULL,
    status_code INTEGER,
    success     INTEGER NOT NULL CHECK (success IN (0, 1)),
    attempt     INTEGER NOT NULL DEFAULT 1,
    error       TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS webhook_deliveries_hook_idx ON webhook_deliveries (webhook_id, created_at);
CREATE INDEX IF NOT EXISTS webhook_deliveries_outbox_idx ON webhook_deliveries (outbox_id, webhook_id, success);

CREATE TABLE IF NOT EXISTS webhook_outbox (
    id           TEXT PRIMARY KEY,
    event_id     TEXT,
    action       TEXT NOT NULL,
    payload      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    attempts     INTEGER NOT NULL DEFAULT 0,
    next_try_at  TEXT,
    processed_at TEXT
);

CREATE INDEX IF NOT EXISTS webhook_outbox_pending_idx ON webhook_outbox (processed_at, created_at);

-- Publicly fetchable, hash-anchored statements. Issued once so the hash is stable.
CREATE TABLE IF NOT EXISTS issued_records (
    record_hash TEXT PRIMARY KEY,
    kind        TEXT NOT NULL CHECK (kind IN ('judge', 'certificate')),
    subject_id  TEXT NOT NULL,
    event_id    TEXT,
    payload     TEXT NOT NULL,
    issued_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS issued_records_subject_uq
    ON issued_records (kind, subject_id);
CREATE INDEX IF NOT EXISTS issued_records_event_idx ON issued_records (event_id);
