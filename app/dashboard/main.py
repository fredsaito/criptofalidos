"""
CriptoFalidos — Product Trend Dashboard
Main overview page.
"""

from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import text

from app.database import SessionLocal, init_db

st.set_page_config(
    page_title="CriptoFalidos — Trend Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

_LATEST_SNAPSHOT_SQL = text("""
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
def load_data() -> pd.DataFrame:
    db = SessionLocal()
    try:
        result = db.execute(_LATEST_SNAPSHOT_SQL)
        rows = result.fetchall()
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows, columns=result.keys())
        df["captured_at"] = pd.to_datetime(df["captured_at"])
        return df
    finally:
        db.close()


def main() -> None:
    init_db()

    st.title("📈 CriptoFalidos — Product Trend Dashboard")
    st.caption("Real-time product opportunity analysis · Google Trends × Amazon")

    with st.spinner("Loading data…"):
        df = load_data()

    if df.empty:
        st.warning("No data yet.")
        st.info(
            "Start the scheduler to collect data:\n"
            "```\ndocker compose up scheduler\n```\n"
            "or locally:\n"
            "```\npython -m app.scheduler.run\n```"
        )
        return

    # ── KPIs ──────────────────────────────────────────────────────────────────
    now = datetime.utcnow()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Products Tracked", len(df))
    col2.metric(
        "Updated (24 h)",
        int((df["captured_at"] >= now - timedelta(days=1)).sum()),
    )
    col3.metric("Avg Trend Score", f"{df['trend_score'].mean():.1f}")
    col4.metric(
        "High Opportunity (≥70)",
        int((df["opportunity_score"] >= 70).sum()),
    )

    st.divider()

    # ── Charts ────────────────────────────────────────────────────────────────
    left, right = st.columns(2)

    with left:
        st.subheader("Top 10 by Trend Score")
        top10 = (
            df.nlargest(10, "trend_score")
            .assign(label=lambda d: d["name"].str[:45])
        )
        fig = px.bar(
            top10,
            x="trend_score",
            y="label",
            color="category",
            orientation="h",
            labels={"trend_score": "Trend Score", "label": ""},
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.update_layout(height=380, showlegend=True, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.subheader("Virality vs Demand Matrix")
        fig = px.scatter(
            df,
            x="virality_score",
            y="demand_score",
            color="category",
            size="opportunity_score",
            size_max=30,
            hover_name="name",
            hover_data={
                "trend_score": ":.1f",
                "amazon_rank": True,
                "tiktok_views": ":,",  # synthetic view count derived from Google Trends score
                "category": False,
            },
            labels={"virality_score": "Google Trends Interest (0–100)", "demand_score": "Amazon Demand (0–100)"},
            color_discrete_sequence=px.colors.qualitative.Pastel,
        )
        fig.add_vline(x=50, line_dash="dash", line_color="rgba(150,150,150,0.5)")
        fig.add_hline(y=50, line_dash="dash", line_color="rgba(150,150,150,0.5)")
        fig.update_layout(height=380)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # ── Score distribution ────────────────────────────────────────────────────
    with st.expander("Score Distribution"):
        fig = px.histogram(
            df,
            x="opportunity_score",
            nbins=20,
            color="source",
            labels={"opportunity_score": "Opportunity Score"},
            color_discrete_map={"amazon": "#FF9900", "tiktok": "#010101", "both": "#69C9D0"},
        )
        fig.update_layout(height=280)
        st.plotly_chart(fig, use_container_width=True)

    # ── Data table ────────────────────────────────────────────────────────────
    st.subheader("All Tracked Products")

    f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
    with f_col1:
        cats = ["All"] + sorted(df["category"].dropna().unique().tolist())
        cat_filter = st.selectbox("Category", cats)
    with f_col2:
        srcs = ["All"] + sorted(df["source"].dropna().unique().tolist())
        src_filter = st.selectbox("Source", srcs)
    with f_col3:
        min_score = st.number_input("Min Opportunity", 0, 100, 0)

    fdf = df.copy()
    if cat_filter != "All":
        fdf = fdf[fdf["category"] == cat_filter]
    if src_filter != "All":
        fdf = fdf[fdf["source"] == src_filter]
    fdf = fdf[fdf["opportunity_score"] >= min_score]

    display = fdf.sort_values("opportunity_score", ascending=False)[
        ["name", "category", "source", "opportunity_score", "trend_score",
         "virality_score", "demand_score", "amazon_rank", "tiktok_views"]
    ]

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "name": st.column_config.TextColumn("Product", width="large"),
            "opportunity_score": st.column_config.ProgressColumn("Opportunity", max_value=100, format="%.1f"),
            "trend_score": st.column_config.ProgressColumn("Trend", max_value=100, format="%.1f"),
            "virality_score": st.column_config.ProgressColumn("Virality", max_value=100, format="%.1f"),
            "demand_score": st.column_config.ProgressColumn("Demand", max_value=100, format="%.1f"),
            "tiktok_views": st.column_config.NumberColumn("Trend Interest (est. views)", format="%d"),
        },
    )

    last_update = df["captured_at"].max()
    st.caption(f"Last collection: {last_update.strftime('%Y-%m-%d %H:%M UTC')}")


if __name__ == "__main__":
    main()
