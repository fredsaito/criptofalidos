"""
Amazon Best Sellers collector.

Scrapes public Amazon Best Sellers pages (no API key required).
Rotates user-agents and adds delays to reduce blocking risk.
"""

import random
import time
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseCollector

CATEGORIES: Dict[str, str] = {
    "Electronics": "https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/",
    "Kitchen": "https://www.amazon.com/Best-Sellers-Kitchen-Dining/zgbs/kitchen/",
    "Beauty": "https://www.amazon.com/Best-Sellers-Beauty/zgbs/beauty/",
    "Sports": "https://www.amazon.com/Best-Sellers-Sports-Outdoors/zgbs/sporting-goods/",
    "Toys": "https://www.amazon.com/Best-Sellers-Toys-Games/zgbs/toys-and-games/",
    "Home": "https://www.amazon.com/Best-Sellers-Home-Garden/zgbs/garden/",
    "Health": "https://www.amazon.com/Best-Sellers-Health-Personal-Care/zgbs/hpc/",
    "Pet Supplies": "https://www.amazon.com/Best-Sellers-Pet-Supplies/zgbs/pet-supplies/",
}

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class AmazonCollector(BaseCollector):
    """Scrapes Amazon Best Sellers pages for top products."""

    def __init__(self) -> None:
        super().__init__()
        self._session = requests.Session()

    def collect(self) -> List[Dict]:
        results: List[Dict] = []
        for category, url in CATEGORIES.items():
            try:
                products = self._scrape_category(category, url)
                results.extend(products)
                self.logger.info(f"Amazon: {category} → {len(products)} products")
            except Exception as e:
                self.logger.error(f"Amazon error for {category}: {e}")
            time.sleep(random.uniform(2.5, 4.5))
        return results

    def _scrape_category(self, category: str, url: str) -> List[Dict]:
        self._session.headers.update({
            "User-Agent": random.choice(_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": "1",
        })

        resp = self._session.get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "lxml")

        # Amazon uses different grid selectors; try multiple
        items = (
            soup.select("div.zg-grid-general-faceout")
            or soup.select("li.zg-item-immersion")
            or soup.select("div[data-asin]")
        )

        products: List[Dict] = []
        for rank, item in enumerate(items[:20], start=1):
            product = self._parse_item(item, category, rank)
            if product:
                products.append(product)
        return products

    def _parse_item(self, item, category: str, rank: int) -> Optional[Dict]:
        try:
            name = self._extract_name(item)
            if not name:
                return None

            asin = item.get("data-asin") or self._extract_asin_from_link(item)
            rating = self._extract_rating(item)
            price = self._extract_price(item)
            reviews = self._extract_reviews(item)
            image_url = self._extract_image(item)

            return {
                "name": name,
                "category": category,
                "asin": asin or None,
                "amazon_rank": rank,
                "amazon_rating": rating,
                "amazon_price": price,
                "amazon_reviews": reviews,
                "image_url": image_url,
                "product_url": f"https://www.amazon.com/dp/{asin}" if asin else "",
            }
        except Exception as e:
            self.logger.debug(f"Parse error at rank {rank}: {e}")
            return None

    # ── helpers ──────────────────────────────────────────────────────────────

    def _extract_name(self, item) -> str:
        for sel in [
            "div._cDEzb_p13n-sc-css-line-clamp-3_g3dy1",
            "div.p13n-sc-truncated",
            "span.zg-text-center-align",
            "a.a-link-normal span",
            "div[class*='truncate']",
        ]:
            el = item.select_one(sel)
            if el:
                return el.get_text(strip=True)[:300]
        return ""

    def _extract_asin_from_link(self, item) -> str:
        link = item.select_one("a.a-link-normal[href*='/dp/']")
        if link:
            href = link.get("href", "")
            if "/dp/" in href:
                return href.split("/dp/")[1].split("/")[0].split("?")[0]
        return ""

    def _extract_rating(self, item) -> Optional[float]:
        el = item.select_one("span.a-icon-alt")
        if el:
            try:
                return float(el.get_text(strip=True).split()[0])
            except (ValueError, IndexError):
                pass
        return None

    def _extract_price(self, item) -> Optional[float]:
        for sel in ["span._cDEzb_p13n-sc-price_3mJ9Z", "span.p13n-sc-price", "span.a-price-whole"]:
            el = item.select_one(sel)
            if el:
                try:
                    return float(el.get_text(strip=True).replace("$", "").replace(",", ""))
                except ValueError:
                    pass
        return None

    def _extract_reviews(self, item) -> int:
        for sel in ["span.a-size-small", "span[aria-label*='stars']"]:
            el = item.select_one(sel)
            if el:
                text = el.get_text(strip=True).replace(",", "")
                try:
                    return int(text)
                except ValueError:
                    pass
        return 0

    def _extract_image(self, item) -> str:
        el = item.select_one("img")
        if el:
            return el.get("src") or el.get("data-src") or ""
        return ""
