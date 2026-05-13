"""
TikTok trend collector.

Uses TikTok's public hashtag detail API to fetch view/post counts for
product-related hashtags. No auth required; rate-limited to 1 req/s.
For high-volume production use, switch to the TikTok Research API.
"""

import time
from typing import Dict, List, Optional

import requests

from .base import BaseCollector

# Product-adjacent hashtags to track across TikTok
PRODUCT_HASHTAGS = [
    "amazonfind",
    "amazonfinds",
    "tiktokmademebuyit",
    "musthave",
    "viralproducts",
    "techgadgets",
    "kitchengadgets",
    "beautyfinds",
    "homeessentials",
    "gadgets",
    "lifehack",
    "cleaninghacks",
    "organizationhacks",
    "workfromhome",
    "fitnessproducts",
    "petproducts",
    "kidsproducts",
    "healthproducts",
]

_HASHTAG_API = "https://www.tiktok.com/api/challenge/detail/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.tiktok.com/",
}


class TikTokCollector(BaseCollector):
    """Collects trending product signals from TikTok hashtags."""

    def __init__(self) -> None:
        super().__init__()
        self._session = requests.Session()
        self._session.headers.update(_HEADERS)

    def collect(self) -> List[Dict]:
        results: List[Dict] = []
        for hashtag in PRODUCT_HASHTAGS:
            data = self._get_hashtag_stats(hashtag)
            if data:
                results.append(data)
            time.sleep(1.2)  # Respect rate limits
        self.logger.info(f"TikTok: collected {len(results)}/{len(PRODUCT_HASHTAGS)} hashtags")
        return results

    def _get_hashtag_stats(self, hashtag: str) -> Optional[Dict]:
        params = {"challengeName": hashtag, "appId": "1233"}
        try:
            resp = self._session.get(_HASHTAG_API, params=params, timeout=10)
            resp.raise_for_status()
            body = resp.json()

            challenge = body.get("challengeInfo", {}).get("challenge", {})
            stats = body.get("challengeInfo", {}).get("stats", {})

            views = int(stats.get("viewCount", 0))
            posts = int(stats.get("videoCount", 0))

            if views == 0 and posts == 0:
                return None

            return {
                "hashtag": hashtag,
                "title": challenge.get("title", hashtag),
                "views": views,
                "posts": posts,
            }
        except requests.exceptions.HTTPError as e:
            self.logger.warning(f"TikTok HTTP error for #{hashtag}: {e}")
        except Exception as e:
            self.logger.warning(f"TikTok error for #{hashtag}: {e}")
        return None
