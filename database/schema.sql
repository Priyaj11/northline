-- Northline certification data store.
--
-- This is NOT ParaBank's database. ParaBank owns its own HyperSQL store.
-- Northline extracts accounts and transactions from ParaBank's REST services
-- into these tables and performs all SQL validation and settlement
-- reconciliation here.
--
-- That mirrors how a bank actually works: the core banking system owns its
-- data, and the reconciliation and settlement engine reads an extract of it
-- rather than querying the core directly.
--
-- Money is NUMERIC(15,2), never a floating point type. A float cannot
-- represent 0.01 exactly, so a ledger stored in floats accumulates error that
-- looks like a reconciliation break and is not, while hiding real one cent
-- errors that are. NUMERIC is exact decimal arithmetic.

CREATE TABLE IF NOT EXISTS extraction_runs (
    run_id            BIGSERIAL PRIMARY KEY,
    environment       TEXT        NOT NULL,
    release           TEXT        NOT NULL,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    account_count     INTEGER,
    transaction_count INTEGER,
    status            TEXT        NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS accounts (
    account_id   BIGINT         PRIMARY KEY,
    customer_id  BIGINT         NOT NULL,
    account_type TEXT           NOT NULL,
    balance      NUMERIC(15,2)  NOT NULL,
    run_id       BIGINT         REFERENCES extraction_runs(run_id) ON DELETE SET NULL,
    extracted_at TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id   BIGINT         PRIMARY KEY,
    account_id       BIGINT         NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    transaction_type TEXT           NOT NULL,
    transaction_date TIMESTAMPTZ    NOT NULL,
    amount           NUMERIC(15,2)  NOT NULL,
    description      TEXT,
    run_id           BIGINT         REFERENCES extraction_runs(run_id) ON DELETE SET NULL,
    extracted_at     TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS transactions_account_idx ON transactions (account_id);
CREATE INDEX IF NOT EXISTS transactions_date_idx    ON transactions (transaction_date);
CREATE INDEX IF NOT EXISTS accounts_customer_idx    ON accounts (customer_id);
