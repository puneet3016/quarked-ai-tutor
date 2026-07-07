-- migration_v5: budget alert dedup table
-- Ensures each monthly budget threshold email (80%, 95%) is sent at most once per month.
-- Idempotent — safe to run more than once.

CREATE TABLE IF NOT EXISTS budget_alerts (
    month     text        NOT NULL,   -- 'YYYY-MM'
    threshold int         NOT NULL,   -- 80, 95
    sent_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (month, threshold)
);
