"""
Social trend collector using Google Trends (via pytrends).

Replaces the TikTok hashtag API, which now returns empty responses due to
bot-blocking. Google Trends provides the same signal — how much interest a
product search is generating — and needs no API key.

Return format is identical to the old TikTok collector so nothing downstream
needs to change. "views" and "posts" are synthetic values derived from the
0-100 Google Trends interest score using a log scale.
"""

import math
import time
from typing import Dict, List

from pytrends.request import TrendReq

from .base import BaseCollector

PRODUCT_TERMS = [
    "amazon finds",
    "viral products",
    "tech gadgets",
    "kitchen gadgets",
    "beauty products",
    "fitness products",
    "home organization",
    "pet products",
    "kids toys",
    "health products",
    "tiktok products",
    "must have products",
    "cool gadgets",
    "cleaning hacks",
    "work from home products",
]

# Google Trends score (0–100) → synthetic view count using log scale
# score 100 → ~1B,  score 50 → ~32M,  score 10 → ~1M
def _to_views(score: float) -> int:
    if score <= 0:
        return 0
    return int(10 ** (score / 100 * 5 + 4))


def _to_posts(score: float) -> int:
    if score <= 0:
        return 0
    return int(score / 100 * 500_000)


class TikTokCollector(BaseCollector):
    """
    Social trend collector backed by Google Trends.
    Named TikTokCollector to keep existing imports unchanged.
    """

    def __init__(self) -> None:
        super().__init__()
        self._pytrend = TrendReq(
            hl="en-US",
            tz=360,
            timeout=(10, 25),
            retries=2,
            backoff_factor=0.1,
        )

    def collect(self) -> List[Dict]:
        results: List[Dict] = []
        # pytrends max 5 keywords per request
        for i in range(0, len(PRODUCT_TERMS), 5):
            batch = PRODUCT_TERMS[i : i + 5]
            results.extend(self._fetch_batch(batch))
            time.sleep(2.5)
        self.logger.info(
            "Google Trends: collected %d/%d terms", len(results), len(PRODUCT_TERMS)
        )
        return results

    def _fetch_batch(self, terms: List[str]) -> List[Dict]:
        try:
            self._pytrend.build_payload(terms, cat=0, timeframe="now 7-d", geo="US")
            data = self._pytrend.interest_over_time()
            results = []
            for term in terms:
                if term not in data.columns:
                    continue
                score = float(data[term].mean())
                if score <= 0:
                    continue
                results.append({
                    "hashtag": term.replace(" ", ""),
                    "title": term,
                    "views": _to_views(score),
                    "posts": _to_posts(score),
                })
            return results
        except Exception as e:
            self.logger.warning("Google Trends error for %s: %s", terms, e)
            return []
