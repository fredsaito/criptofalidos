from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(500), nullable=False)
    category = Column(String(200), index=True)
    source = Column(String(50), nullable=False)  # 'tiktok', 'amazon', 'both'
    asin = Column(String(20), unique=True, nullable=True)
    tiktok_hashtag = Column(String(200), nullable=True)
    image_url = Column(Text, nullable=True)
    product_url = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    snapshots = relationship("TrendSnapshot", back_populates="product", lazy="dynamic")
    alerts = relationship("Alert", back_populates="product")


class TrendSnapshot(Base):
    __tablename__ = "trend_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    captured_at = Column(DateTime, default=datetime.utcnow, index=True)

    # TikTok metrics
    tiktok_views = Column(BigInteger, default=0)
    tiktok_posts = Column(Integer, default=0)

    # Amazon metrics
    amazon_rank = Column(Integer, nullable=True)
    amazon_reviews = Column(Integer, default=0)
    amazon_rating = Column(Float, nullable=True)
    amazon_price = Column(Float, nullable=True)

    # Computed scores (all 0–100)
    trend_score = Column(Float, default=0.0)
    opportunity_score = Column(Float, default=0.0)
    virality_score = Column(Float, default=0.0)
    demand_score = Column(Float, default=0.0)

    product = relationship("Product", back_populates="snapshots")

    __table_args__ = (
        Index("ix_snapshots_product_captured", "product_id", "captured_at"),
    )


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    alert_type = Column(String(50))  # 'high_opportunity', 'score_spike'
    message = Column(Text)
    trend_score = Column(Float)
    was_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="alerts")
