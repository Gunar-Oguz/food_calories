"""Streamlit dashboard that searches the processed food data.

Data comes from S3 by default. Set DATA_PATH to a local parquet file to run without AWS:
    DATA_PATH=data/sample_processed.parquet streamlit run app.py
"""
import io
import os
from datetime import datetime

import boto3
import pandas as pd
import streamlit as st

BUCKET = os.getenv("S3_BUCKET", "food-etl-bucket-gulnar")
PROCESSED_KEY = "write/processed_data.parquet"

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
    """Read the processed dataset from a local file (DATA_PATH) or from S3."""
    local_path = os.getenv("DATA_PATH")
    if local_path:
        return pd.read_parquet(local_path)
    obj = boto3.client("s3").get_object(Bucket=BUCKET, Key=PROCESSED_KEY)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


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
    st.markdown("A small data pipeline: OpenFoodFacts API → AWS S3 → ETL → Streamlit")

    st.sidebar.header("⚙️ Controls")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.sidebar.markdown("---")
    source = f"local file `{os.getenv('DATA_PATH')}`" if os.getenv("DATA_PATH") else f"`s3://{BUCKET}`"
    st.sidebar.markdown(f"**Data source:** {source}")
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
        st.bar_chart(df[NUTRIENTS].mean())

    st.markdown("---")
    st.caption(f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
