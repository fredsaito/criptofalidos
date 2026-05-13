"""
Core collection job — runs every 4 hours.

Flow:
  1. Collect TikTok hashtag stats
  2. Scrape Amazon Best Sellers
  3. Upsert products and create trend snapshots
  4. Calculate opportunity scores
  5. Fire Telegram alerts for high-scoring products
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.alerts.telegram import TelegramAlerter
from app.collectors.amazon import AmazonCollector
from app.collectors.tiktok import TikTokCollector
from app.config import settings
from app.database import get_db_session
from app.models import Alert, Product, TrendSnapshot
from app.scoring.trend_score import calculate_scores

logger = logging.getLogger(__name__)

# Category → TikTok hashtag keyword mappings for cross-platform matching
_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "electronics": ["tech", "gadget", "electronic"],
    "kitchen": ["kitchen", "cooking", "food"],
    "beauty": ["beauty", "makeup", "skincare", "hair"],
    "sports": ["sport", "fitness", "gym", "workout"],
    "toys": ["toy", "kids", "children", "game"],
    "home": ["home", "house", "decor", "organization"],
    "health": ["health", "wellness", "vitamin"],
    "pet supplies": ["pet", "dog", "cat"],
}


def run_collection() -> None:
    logger.info("Starting trend collection at %s UTC", datetime.utcnow().isoformat())

    tiktok_data = _collect_tiktok()
    amazon_data = _collect_amazon()

    with get_db_session() as db:
        snapshots = _process_and_store(db, tiktok_data, amazon_data)
        _fire_alerts(db, snapshots)

    logger.info("Collection complete — %d snapshots stored", len(snapshots))


# ── collectors ────────────────────────────────────────────────────────────────

def _collect_tiktok() -> List[Dict]:
    try:
        return TikTokCollector().collect()
    except Exception as e:
        logger.error("TikTok collection failed: %s", e)
        return []


def _collect_amazon() -> List[Dict]:
    try:
        return AmazonCollector().collect()
    except Exception as e:
        logger.error("Amazon collection failed: %s", e)
        return []


# ── processing ────────────────────────────────────────────────────────────────

def _process_and_store(
    db: Session,
    tiktok_data: List[Dict],
    amazon_data: List[Dict],
) -> List[TrendSnapshot]:
    tiktok_by_hashtag = {item["hashtag"]: item for item in tiktok_data}
    snapshots: List[TrendSnapshot] = []

    # Amazon products (possibly enriched with TikTok signals)
    for item in amazon_data:
        product = _upsert_amazon_product(db, item)
        views, posts, matched_hashtag = _match_tiktok(item["category"], tiktok_by_hashtag)

        if matched_hashtag and product.source == "amazon":
            product.source = "both"
            product.tiktok_hashtag = matched_hashtag

        scores = calculate_scores(
            tiktok_views=views,
            tiktok_posts=posts,
            amazon_rank=item.get("amazon_rank"),
            amazon_reviews=item.get("amazon_reviews", 0),
            amazon_rating=item.get("amazon_rating") or 0.0,
        )
        snap = _create_snapshot(db, product.id, item, views, posts, scores)
        snapshots.append(snap)

    # Pure TikTok trends not already matched
    matched_hashtags = {p.tiktok_hashtag for p in db.query(Product.tiktok_hashtag).all() if p.tiktok_hashtag}
    for item in tiktok_data:
        if item["hashtag"] in matched_hashtags:
            continue
        product = _upsert_tiktok_product(db, item)
        scores = calculate_scores(tiktok_views=item["views"], tiktok_posts=item["posts"])
        snap = TrendSnapshot(
            product_id=product.id,
            tiktok_views=item["views"],
            tiktok_posts=item["posts"],
            **scores,
        )
        db.add(snap)
        db.flush()
        snapshots.append(snap)

    db.commit()
    return snapshots


def _create_snapshot(
    db: Session,
    product_id: int,
    amazon_item: Dict,
    tiktok_views: int,
    tiktok_posts: int,
    scores: Dict,
) -> TrendSnapshot:
    snap = TrendSnapshot(
        product_id=product_id,
        tiktok_views=tiktok_views,
        tiktok_posts=tiktok_posts,
        amazon_rank=amazon_item.get("amazon_rank"),
        amazon_reviews=amazon_item.get("amazon_reviews", 0),
        amazon_rating=amazon_item.get("amazon_rating"),
        amazon_price=amazon_item.get("amazon_price"),
        **scores,
    )
    db.add(snap)
    db.flush()
    return snap


# ── upsert helpers ────────────────────────────────────────────────────────────

def _upsert_amazon_product(db: Session, item: Dict) -> Product:
    product: Optional[Product] = None
    if item.get("asin"):
        product = db.query(Product).filter_by(asin=item["asin"]).first()
    if not product:
        product = db.query(Product).filter_by(name=item["name"], category=item.get("category")).first()
    if product:
        product.updated_at = datetime.utcnow()
        if item.get("image_url"):
            product.image_url = item["image_url"]
        return product

    product = Product(
        name=item["name"],
        category=item.get("category"),
        source="amazon",
        asin=item.get("asin") or None,
        image_url=item.get("image_url"),
        product_url=item.get("product_url"),
    )
    db.add(product)
    db.flush()
    return product


def _upsert_tiktok_product(db: Session, item: Dict) -> Product:
    product = db.query(Product).filter_by(tiktok_hashtag=item["hashtag"]).first()
    if product:
        return product
    product = Product(
        name=f"#{item['hashtag']}",
        category="TikTok Trend",
        source="tiktok",
        tiktok_hashtag=item["hashtag"],
    )
    db.add(product)
    db.flush()
    return product


# ── matching ──────────────────────────────────────────────────────────────────

def _match_tiktok(
    category: str,
    tiktok_map: Dict[str, Dict],
) -> tuple:
    """Return (max_views, max_posts, best_hashtag) for a given Amazon category."""
    cat = category.lower()
    best_views, best_posts, best_hashtag = 0, 0, None

    for hashtag, data in tiktok_map.items():
        keywords = next(
            (kws for cat_key, kws in _CATEGORY_KEYWORDS.items() if cat_key in cat),
            [],
        )
        if any(kw in hashtag.lower() for kw in keywords) or hashtag in cat:
            if data["views"] > best_views:
                best_views = data["views"]
                best_posts = data["posts"]
                best_hashtag = hashtag

    return best_views, best_posts, best_hashtag


# ── alerts ────────────────────────────────────────────────────────────────────

def _fire_alerts(db: Session, snapshots: List[TrendSnapshot]) -> None:
    alerter = TelegramAlerter()
    cooldown = timedelta(hours=24)

    for snap in snapshots:
        if snap.opportunity_score < settings.ALERT_THRESHOLD:
            continue

        # Skip if we already alerted for this product within 24 h
        last = (
            db.query(Alert)
            .filter_by(product_id=snap.product_id, alert_type="high_opportunity")
            .order_by(Alert.created_at.desc())
            .first()
        )
        if last and (datetime.utcnow() - last.created_at) < cooldown:
            continue

        product = db.query(Product).get(snap.product_id)
        msg = (
            f"🔥 <b>High Opportunity Alert</b>\n\n"
            f"<b>{product.name}</b>\n"
            f"Category: {product.category}\n"
            f"Opportunity Score: <b>{snap.opportunity_score:.1f}/100</b>\n"
            f"TikTok Views: {snap.tiktok_views:,}\n"
            f"Amazon BSR: #{snap.amazon_rank or 'N/A'}\n"
        )
        if product.product_url:
            msg += f"\n{product.product_url}"

        alert = Alert(
            product_id=snap.product_id,
            alert_type="high_opportunity",
            message=msg,
            trend_score=snap.opportunity_score,
        )
        db.add(alert)

        try:
            alert.was_sent = alerter.send(msg)
        except Exception as e:
            logger.error("Alert send error: %s", e)

    db.commit()
