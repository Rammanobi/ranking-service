import os

# Where the SQLite file lives. Override with env var for tests / deployment.
DB_PATH = os.environ.get("RANKING_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data.db"))

# --- Validation bounds ---
MIN_TRANSACTION_AMOUNT = 0.01
MAX_TRANSACTION_AMOUNT = 100_000.0
MAX_USER_ID_LEN = 64
MAX_IDEMPOTENCY_KEY_LEN = 128

# --- Abuse / rate-limit controls ---
# Max transactions a single user may submit within RATE_LIMIT_WINDOW_SECONDS.
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

# Ranking formula weights (see app/ranking.py for the full explanation).
RANKING_WEIGHT_POINTS = 0.7
RANKING_WEIGHT_CONSISTENCY = 0.3
CONSISTENCY_POINTS_PER_ACTIVE_DAY = 10

# A single transaction can only contribute this much to the *ranking* score,
# even if its raw point value is larger. This caps "whale" manipulation where
# one huge transaction dominates the leaderboard. The full amount is still
# recorded and shown in /summary; only the ranking contribution is capped.
MAX_RANKING_CONTRIBUTION_PER_TRANSACTION = 5_000.0
