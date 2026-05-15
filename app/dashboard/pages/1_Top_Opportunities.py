"""
Top 10 Product Opportunities page.
Ranked by opportunity_score — products with high Google Trends interest
that haven't yet been dominated on Amazon.
"""

from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import text

from app.database import SessionLocal

st.set_page_config(
    page_title="Top Opportunities — CriptoFalidos",
    page_icon="🎯",
    layout="wide",
)

_SQL = text("""
    SELECT DISTINCT ON (p.id)
        p.id,
        p.name,
        p.category,
        p.source,
        p.asin,
        p.tiktok_hashtag,
        p.product_url,
        p.image_url,
        ts.captured_at,
        ts.tiktok_views,
        ts.tiktok_posts,
        ts.amazon_rank,
        ts.amazon_reviews,
        ts.amazon_rating,
        ts.amazon_price,
        ts.trend_score,
        ts.opportunity_score,
        ts.virality_score,
        ts.demand_score
    FROM products p
    JOIN trend_snapshots ts ON p.id = ts.product_id
    WHERE p.is_active = TRUE
    ORDER BY p.id, ts.captured_at DESC
""")


@st.cache_data(ttl=300)
def load_top10() -> pd.DataFrame:
    db = SessionLocal()
    try:
        result = db.execute(_SQL)
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=result.keys())
        df["captured_at"] = pd.to_datetime(df["captured_at"])
        return df.nlargest(10, "opportunity_score").reset_index(drop=True)
    finally:
        db.close()


_RANK_COLORS = {1: "#FFD700", 2: "#C0C0C0", 3: "#CD7F32"}
_SCORE_GRADIENT = "linear-gradient(135deg, #667eea 0%, #764ba2 100%)"


def _badge(rank: int) -> str:
    color = _RANK_COLORS.get(rank, "#4CAF50")
    return (
        f'<div style="background:{color};color:white;border-radius:50%;'
        f'width:52px;height:52px;display:flex;align-items:center;justify-content:center;'
        f'font-size:22px;font-weight:700;margin:auto">{rank}</div>'
    )


def _score_box(score: float) -> str:
    return (
        f'<div style="text-align:center;padding:12px 16px;'
        f'background:{_SCORE_GRADIENT};border-radius:12px;color:white">'
        f'<div style="font-size:13px;opacity:.85">Opportunity</div>'
        f'<div style="font-size:46px;font-weight:800;line-height:1">{score:.0f}</div>'
        f'<div style="font-size:13px;opacity:.85">/ 100</div></div>'
    )


def render_card(row: pd.Series, rank: int) -> None:
    with st.container():
        c1, c2, c3 = st.columns([0.6, 3.5, 1.6])

        with c1:
            st.markdown(_badge(rank), unsafe_allow_html=True)

        with c2:
            name = row["name"][:65] + ("…" if len(row["name"]) > 65 else "")
            st.markdown(f"### {name}")
            st.markdown(
                f"**{row['category']}** · "
                f"source: `{row['source'].upper()}`"
            )

            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown(f"Google Trends Interest **{row['virality_score']:.0f}/100**")
                st.progress(float(row["virality_score"]) / 100)
            with sc2:
                st.markdown(f"Amazon Demand **{row['demand_score']:.0f}/100**")
                st.progress(float(row["demand_score"]) / 100)

            details = []
            if row.get("tiktok_views", 0):
                details.append(f"Google Trends: **{int(row['tiktok_views']):,}** est. monthly searches · **{int(row['tiktok_posts']):,}** related queries")
            if row.get("amazon_rank"):
                price_str = f"${row['amazon_price']:.2f}" if row.get("amazon_price") else "N/A"
                rating_str = f"{row['amazon_rating']:.1f}★" if row.get("amazon_rating") else "N/A"
                details.append(
                    f"Amazon BSR: **#{int(row['amazon_rank']):,}** · {rating_str} · {price_str}"
                )
            if details:
                st.caption(" · ".join(details))

        with c3:
            st.markdown(_score_box(row["opportunity_score"]), unsafe_allow_html=True)
            st.write("")
            if row.get("product_url"):
                st.link_button("🛒 Amazon", row["product_url"], use_container_width=True)
            if row.get("tiktok_hashtag"):
                term = row["tiktok_hashtag"].replace("_", "+")
                st.link_button(
                    "📊 Google Trends",
                    f"https://trends.google.com/trends/explore?q={term}&geo=US",
                    use_container_width=True,
                )

    st.divider()


def render_radar(df: pd.DataFrame) -> None:
    """Mini radar/spider chart comparing top-5 products."""
    top5 = df.head(5)
    categories = ["Virality", "Demand", "Trend", "Opportunity"]

    fig = go.Figure()
    for _, row in top5.iterrows():
        label = row["name"][:25]
        fig.add_trace(go.Scatterpolar(
            r=[row["virality_score"], row["demand_score"],
               row["trend_score"], row["opportunity_score"]],
            theta=categories,
            fill="toself",
            name=label,
            opacity=0.6,
        ))

    fig.update_layout(
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        showlegend=True,
        height=380,
        title="Top 5 — Score Radar",
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    st.title("🎯 Top 10 Product Opportunities")
    st.markdown(
        "Products ranked by **Opportunity Score** — high Google Trends interest + "
        "a still-growing Amazon market = prime entry window."
    )

    col_ref, col_btn = st.columns([4, 1])
    with col_btn:
        if st.button("🔄 Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    df = load_top10()

    if df.empty:
        st.warning("No data available yet. Run the scheduler first.")
        return

    with st.expander("How is the Opportunity Score calculated?", expanded=False):
        st.markdown("""
        | Component | Weight | Signal |
        |-----------|--------|--------|
        | Component | Weight | Signal |
        |-----------|--------|--------|
        | Google Trends Interest | 60% | 7-day search interest score (0–100) |
        | Amazon Demand          | 40% | Inverse Best Seller Rank |
        | Opportunity Bonus      | +0–20 pts | High interest + mid-tier BSR (50–500) |

        **Sweet spot**: Google Trends interest > 50 *and* Amazon BSR between 50–500.
        This means the product is actively being searched but Amazon sellers haven't
        fully saturated the listing yet — the best entry window.
        """)

    st.divider()

    # Cards
    for idx, row in df.iterrows():
        render_card(row, idx + 1)

    # Radar comparison
    if len(df) >= 3:
        render_radar(df)

    # Full table
    with st.expander("Full data table"):
        st.dataframe(
            df[[
                "name", "category", "source", "opportunity_score", "trend_score",
                "virality_score", "demand_score", "tiktok_views",
                "amazon_rank", "amazon_rating", "amazon_price",
            ]].rename(columns={"opportunity_score": "Opportunity", "trend_score": "Trend"}),
            use_container_width=True,
            hide_index=True,
        )

    last = df["captured_at"].max()
    st.caption(f"Last collection: {last.strftime('%Y-%m-%d %H:%M UTC')}")


if __name__ == "__main__":
    main()
