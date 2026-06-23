"""
SQLite access layer.

Why SQLite instead of a plain in-memory dict:
- Transactions need to be durable and atomic. SQLite gives us real ACID
  transactions "for free" without standing up Postgres for a take-home.
- The UNIQUE constraint on idempotency_key is what makes duplicate-request
  prevention airtight even under concurrent requests (see insert_transaction).
- WAL mode lets reads (GET /summary, GET /ranking) proceed without blocking
  on writes.

Concurrency model:
- A single process-wide `threading.Lock` (WRITE_LOCK) serializes all writes.
  SQLite already serializes writes internally, but wrapping our
  check-then-insert sequence in an explicit lock turns "insert if not
  duplicate, then update aggregates" into one atomic unit from the
  application's point of view, which a bare DB transaction alone would not
  guarantee against a race between two threads both passing the duplicate
  check before either commits.
- This is a single-process design. For multi-process/horizontal scaling the
  lock would need to be replaced by relying solely on the DB's UNIQUE
  constraint + retry-on-IntegrityError (the code already falls back to that
  path -- see insert_transaction), or a distributed lock (e.g. Redis).
"""

import sqlite3
import threading
from contextlib import contextmanager

from . import config

WRITE_LOCK = threading.Lock()

_local = threading.local()


def get_connection():
    """One SQLite connection per thread, reused across requests."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        _local.conn = conn
    return conn


@contextmanager
def transaction():
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         TEXT NOT NULL,
            amount          REAL NOT NULL,
            idempotency_key TEXT NOT NULL UNIQUE,
            created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            active_date     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%d','now'))
        );

        CREATE INDEX IF NOT EXISTS idx_transactions_user_id ON transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_transactions_user_created
            ON transactions(user_id, created_at);

        CREATE TABLE IF NOT EXISTS user_summary (
            user_id          TEXT PRIMARY KEY,
            total_points     REAL NOT NULL DEFAULT 0,
            capped_points    REAL NOT NULL DEFAULT 0,
            transaction_count INTEGER NOT NULL DEFAULT 0,
            active_days      INTEGER NOT NULL DEFAULT 0,
            ranking_points   REAL NOT NULL DEFAULT 0,
            last_active_date TEXT
        );

        CREATE TABLE IF NOT EXISTS user_active_dates (
            user_id     TEXT NOT NULL,
            active_date TEXT NOT NULL,
            PRIMARY KEY (user_id, active_date)
        );
        """
    )
    conn.commit()


def reset_db():
    """Used by tests to start from a clean slate."""
    conn = get_connection()
    conn.executescript("DROP TABLE IF EXISTS transactions; DROP TABLE IF EXISTS user_summary;")
    conn.commit()
    init_db()
