-- smart-suggest database schema
-- Compatible with SQLite 3.x and PostgreSQL 14+

-- ── Users ─────────────────────────────────────────────────────────────────────
CREATE TABLE users (
    id         INTEGER      PRIMARY KEY AUTOINCREMENT,
    username   VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── Items ─────────────────────────────────────────────────────────────────────
CREATE TABLE items (
    id          INTEGER       PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(200)  NOT NULL,
    category    VARCHAR(100)  NOT NULL,
    description VARCHAR(1000),
    created_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── User interactions ─────────────────────────────────────────────────────────
CREATE TABLE user_interactions (
    id        INTEGER   PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER   NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id   INTEGER   NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    action    VARCHAR(20) NOT NULL CHECK (action IN ('view', 'click', 'purchase')),
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interactions_user_id  ON user_interactions(user_id);
CREATE INDEX idx_interactions_item_id  ON user_interactions(item_id);
CREATE INDEX idx_interactions_timestamp ON user_interactions(timestamp);
-- Composite index for the most common query: all actions by a user ordered by time.
CREATE INDEX idx_interactions_user_time ON user_interactions(user_id, timestamp DESC);

-- ── Recommendations ───────────────────────────────────────────────────────────
CREATE TABLE recommendations (
    id        INTEGER     PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item_id   INTEGER     NOT NULL REFERENCES items(id) ON DELETE CASCADE,
    strategy  VARCHAR(20) NOT NULL CHECK (strategy IN ('v1', 'v2')),
    timestamp TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_recommendations_user_id   ON recommendations(user_id);
CREATE INDEX idx_recommendations_item_id   ON recommendations(item_id);
CREATE INDEX idx_recommendations_timestamp ON recommendations(timestamp);
CREATE INDEX idx_recommendations_user_strategy ON recommendations(user_id, strategy);

-- ── A/B tests ─────────────────────────────────────────────────────────────────
CREATE TABLE ab_tests (
    id         INTEGER      PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(200) NOT NULL UNIQUE,
    status     VARCHAR(20)  NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed')),
    created_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ── A/B test assignments ──────────────────────────────────────────────────────
CREATE TABLE ab_test_assignments (
    id         INTEGER   PRIMARY KEY AUTOINCREMENT,
    test_id    INTEGER   NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
    user_id    INTEGER   NOT NULL REFERENCES users(id)    ON DELETE CASCADE,
    variant    CHAR(1)   NOT NULL CHECK (variant IN ('A', 'B')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (test_id, user_id)
);

CREATE INDEX idx_assignments_test_id ON ab_test_assignments(test_id);
CREATE INDEX idx_assignments_user_id ON ab_test_assignments(user_id);

-- ── A/B test results ──────────────────────────────────────────────────────────
CREATE TABLE ab_test_results (
    id          INTEGER      PRIMARY KEY AUTOINCREMENT,
    test_id     INTEGER      NOT NULL REFERENCES ab_tests(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    variant     CHAR(1)      NOT NULL CHECK (variant IN ('A', 'B')),
    value       REAL         NOT NULL
);

CREATE INDEX idx_results_test_id ON ab_test_results(test_id);
-- Composite index for pulling all metrics for a given test+variant at once.
CREATE INDEX idx_results_test_variant ON ab_test_results(test_id, variant);
