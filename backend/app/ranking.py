"""
Ranking calculation.

The leaderboard is intentionally NOT a plain sum of points. A pure sum is
trivial to game: one user could fire a single oversized transaction (or a
burst of automated ones) and jump straight to #1 with no sustained
engagement. Instead we combine two factors:

  ranking_points = (W_POINTS * capped_points) + (W_CONSISTENCY * active_days * POINTS_PER_DAY)

  - capped_points: sum of each transaction's amount, but each individual
    transaction's contribution is capped at MAX_RANKING_CONTRIBUTION_PER_TRANSACTION.
    The user's raw, uncapped total still appears in total_points (shown in
    /summary) -- only the score used for *ranking* is capped. This blunts
    the impact of a single huge or spoofed transaction.
  - active_days: number of distinct calendar days the user has at least one
    transaction on. This rewards sustained, consistent activity over
    one-off spikes, which is harder to fake than a single large value and
    directly resists "dump and rank" abuse.

Weights (config.RANKING_WEIGHT_POINTS / RANKING_WEIGHT_CONSISTENCY) default
to 70/30, favoring points earned while still giving consistency real
influence. These are simple, explainable knobs -- not a hidden ML model --
which keeps the ranking auditable and fair to contestants.
"""

from . import config


def capped_contribution(amount: float) -> float:
    return min(amount, config.MAX_RANKING_CONTRIBUTION_PER_TRANSACTION)


def compute_ranking_points(capped_points_total: float, active_days: int) -> float:
    consistency_component = active_days * config.CONSISTENCY_POINTS_PER_ACTIVE_DAY
    return round(
        config.RANKING_WEIGHT_POINTS * capped_points_total
        + config.RANKING_WEIGHT_CONSISTENCY * consistency_component,
        4,
    )
