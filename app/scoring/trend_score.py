"""
Trend scoring algorithm.

All scores are in the range [0, 100].

- virality_score : TikTok signal — log-scaled view count
- demand_score   : Amazon signal — inverse best-seller rank
- trend_score    : 60% virality + 40% demand
- opportunity_score : trend_score + bonus when TikTok is viral but Amazon
                       rank is mid-tier (product not yet saturated on Amazon)
"""

import math
from typing import Optional


def calculate_scores(
    tiktok_views: int = 0,
    tiktok_posts: int = 0,
    amazon_rank: Optional[int] = None,
    amazon_reviews: int = 0,
    amazon_rating: float = 0.0,
) -> dict:
    virality = _virality_score(tiktok_views)
    demand = _demand_score(amazon_rank)
    trend = round(virality * 0.6 + demand * 0.4, 2)
    opportunity = round(min(100.0, trend + _opportunity_bonus(virality, amazon_rank)), 2)

    return {
        "virality_score": round(virality, 2),
        "demand_score": round(demand, 2),
        "trend_score": trend,
        "opportunity_score": opportunity,
    }


def _virality_score(views: int) -> float:
    """Log-scale: 10k views → ~22pts, 1M → ~55pts, 1B → ~100pts."""
    if views <= 0:
        return 0.0
    # log10(10_000) = 4, log10(1_000_000_000) = 9  →  map [4, 9] → [0, 100]
    raw = (math.log10(max(views, 1)) - 4) / (9 - 4) * 100
    return max(0.0, min(100.0, raw))


def _demand_score(rank: Optional[int]) -> float:
    """Inverse rank: BSR #1 → 100pts, #10k → ~20pts, no rank → 0."""
    if not rank or rank <= 0:
        return 0.0
    if rank <= 10:
        return 100.0
    if rank <= 100:
        return 90.0 - (rank - 10) / 90 * 20   # 90 → 70
    if rank <= 1_000:
        return 70.0 - (rank - 100) / 900 * 30  # 70 → 40
    if rank <= 10_000:
        return 40.0 - (rank - 1_000) / 9_000 * 30  # 40 → 10
    return max(0.0, 10.0 - (rank - 10_000) / 90_000 * 10)


def _opportunity_bonus(virality: float, rank: Optional[int]) -> float:
    """
    Reward high-virality products that haven't yet dominated Amazon.
    Sweet spot: TikTok is exploding (virality > 50) but BSR is mid-tier
    (50–500), meaning the market isn't saturated yet.
    """
    if virality < 40:
        return 0.0
    if rank and 50 <= rank <= 500:
        return 20.0
    if rank and 500 < rank <= 5_000:
        return 10.0
    return 0.0
