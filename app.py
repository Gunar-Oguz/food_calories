"""Streamlit dashboard that searches the processed food data.

Reads data/write/processed_data.parquet, or S3 when S3_BUCKET is set (see storage.py).
"""
from datetime import datetime

import pandas as pd
import streamlit as st

import storage

COLUMN_NAMES = {
    "product_name": "Product",
    "brands": "Brand",
    "calories": "Calories (kcal)",
    "fat": "Fat (g)",
    "sugar": "Sugar (g)",
    "protein": "Proteins (g)",
    "calories_per_gram": "Cal/gram",
}
NUTRIENTS = ["Calories (kcal)", "Fat (g)", "Sugar (g)", "Proteins (g)"]


@st.cache_data(ttl=300)
def load_processed_data():
    """Cached for 5 minutes so every search does not re-read the file."""
    return storage.read_parquet(storage.PROCESSED_KEY)


def search_foods(df, query):
    """Case-insensitive search on product name. regex=False so '(' or '+' in a query can't break it."""
    return df[df["product_name"].str.contains(query, case=False, na=False, regex=False)]


def get_food_data(query="apple"):
    try:
        return search_foods(load_processed_data(), query)
    except Exception as e:
        st.error(f"Could not read the data: {e}")
        return pd.DataFrame()


def main():
    st.set_page_config(page_title="Food Calories Dashboard", page_icon="🥗", layout="wide")
    st.title("🥗 Food Calories & Nutrition Dashboard")
    st.markdown("A small data pipeline: OpenFoodFacts API → fetch → ETL → this dashboard, refreshed daily.")

    st.sidebar.header("⚙️ Controls")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Data source:** `{storage.describe(storage.PROCESSED_KEY)}`")
    st.sidebar.markdown("**Origin:** OpenFoodFacts API")

    search = st.text_input("Enter a food name:", "banana")
    df = get_food_data(search).rename(columns=COLUMN_NAMES)

    if df.empty:
        st.warning("No data found. Try another search term.")
    else:
        st.success(f"✅ Found {len(df)} products for '{search}'")
        st.dataframe(df[["Product", "Brand", *NUTRIENTS, "Cal/gram"]].head(10),
                     use_container_width=True, height=400)

        st.subheader("📊 Nutrition Stats")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Calories", f"{df['Calories (kcal)'].mean():.0f} kcal")
        col2.metric("Avg Fat", f"{df['Fat (g)'].mean():.1f} g")
        col3.metric("Avg Sugar", f"{df['Sugar (g)'].mean():.1f} g")
        col4.metric("Avg Protein", f"{df['Proteins (g)'].mean():.1f} g")
        st.markdown("**Average grams per 100 g**")
        st.bar_chart(df[["Fat (g)", "Sugar (g)", "Proteins (g)"]].mean(), horizontal=True)

    st.markdown("---")
    st.caption(f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
