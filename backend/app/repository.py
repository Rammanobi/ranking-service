"""
Data-access + business logic for transactions and aggregates.

insert_transaction() is the heart of the consistency story:
  1. It runs inside db.WRITE_LOCK, so only one thread in this process can be
     mid-flight through the function at a time.
  2. It runs inside a single SQLite IMMEDIATE transaction, so the insert
     into `transactions` and the upsert into `user_summary` /
     `user_active_dates` either all succeed or all roll back together --
     there is no window where a transaction is recorded but the summary/
     ranking aggregates are stale, and no window where two concurrent
     requests both see "not a duplicate" and both insert.
  3. Duplicate idempotency_key submissions are detected up front via a
     SELECT, and -- belt-and-braces -- the UNIQUE constraint on
     transactions.idempotency_key would raise IntegrityError even if two
     requests somehow raced past the SELECT, which we catch and treat as a
     duplicate rather than an error.
"""

import sqlite3

from . import db, ranking


class DuplicateTransactionError(Exception):
    """Raised when an idempotency_key has already been processed."""

    def __init__(self, existing_row: sqlite3.Row):
        self.existing_row = existing_row


def insert_transaction(user_id: str, amount: float, idempotency_key: str) -> sqlite3.Row:
    with db.WRITE_LOCK:
        conn = db.get_connection()
        existing = conn.execute(
            "SELECT * FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
        ).fetchone()
        if existing is not None:
            raise DuplicateTransactionError(existing)

        try:
            with db.transaction() as tx:
                cur = tx.execute(
                    """
                    INSERT INTO transactions (user_id, amount, idempotency_key)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, amount, idempotency_key),
                )
                row = tx.execute(
                    "SELECT * FROM transactions WHERE id = ?", (cur.lastrowid,)
                ).fetchone()

                tx.execute(
                    """
                    INSERT INTO user_active_dates (user_id, active_date)
                    VALUES (?, ?)
                    ON CONFLICT(user_id, active_date) DO NOTHING
                    """,
                    (user_id, row["active_date"]),
                )
                active_days = tx.execute(
                    "SELECT COUNT(*) AS c FROM user_active_dates WHERE user_id = ?",
                    (user_id,),
                ).fetchone()["c"]

                capped_delta = ranking.capped_contribution(amount)

                tx.execute(
                    """
                    INSERT INTO user_summary (
                        user_id, total_points, capped_points, transaction_count,
                        active_days, ranking_points, last_active_date
                    )
                    VALUES (?, ?, ?, 1, ?, 0, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        total_points = total_points + excluded.total_points,
                        capped_points = capped_points + excluded.capped_points,
                        transaction_count = transaction_count + 1,
                        active_days = excluded.active_days,
                        last_active_date = excluded.last_active_date
                    """,
                    (user_id, amount, capped_delta, active_days, row["active_date"]),
                )

                summary = tx.execute(
                    "SELECT * FROM user_summary WHERE user_id = ?", (user_id,)
                ).fetchone()
                new_ranking_points = ranking.compute_ranking_points(
                    summary["capped_points"], summary["active_days"]
                )
                tx.execute(
                    "UPDATE user_summary SET ranking_points = ? WHERE user_id = ?",
                    (new_ranking_points, user_id),
                )
        except sqlite3.IntegrityError:
            existing = conn.execute(
                "SELECT * FROM transactions WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
            raise DuplicateTransactionError(existing)

        return row


def get_summary(user_id: str) -> sqlite3.Row | None:
    conn = db.get_connection()
    return conn.execute(
        "SELECT * FROM user_summary WHERE user_id = ?", (user_id,)
    ).fetchone()


def get_user_rank(user_id: str) -> int | None:
    conn = db.get_connection()
    row = conn.execute("SELECT ranking_points FROM user_summary WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    better_count = conn.execute(
        "SELECT COUNT(*) AS c FROM user_summary WHERE ranking_points > ?",
        (row["ranking_points"],),
    ).fetchone()["c"]
    return better_count + 1


def get_ranking(limit: int = 100, offset: int = 0) -> list[sqlite3.Row]:
    conn = db.get_connection()
    return conn.execute(
        """
        SELECT user_id, total_points, active_days, ranking_points
        FROM user_summary
        ORDER BY ranking_points DESC, total_points DESC, user_id ASC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
