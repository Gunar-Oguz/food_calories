import streamlit as st
import pandas as pd
import boto3
import io
from datetime import datetime

st.set_page_config(page_title="🥗 Food Calories Dashboard", page_icon="🥗", layout="wide")
st.title("🥗 Food Calories & Nutrition Dashboard")
st.markdown("A full-stack data pipeline: OpenFoodFacts API → AWS S3 → Streamlit Dashboard")

# Sidebar
st.sidebar.header("⚙️ Controls")

if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**Data Source:** AWS S3")
st.sidebar.markdown("**Origin:** OpenFoodFacts API")

@st.cache_data(ttl=300)
def get_food_data(query="apple"):
    """Read processed food data from S3"""
    try:
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket='food-etl-bucket-gulnar', Key='write/processed_data.parquet')
        df = pd.read_parquet(io.BytesIO(obj['Body'].read()))
        df_filtered = df[df['product_name'].str.contains(query, case=False, na=False)]
        return df_filtered
    except Exception as e:
        st.error(f"Error reading from S3: {e}")
        return pd.DataFrame()

# Main content
search = st.text_input("Enter a food name:", "banana")
df = get_food_data(search)

if df.empty:
    st.warning("No data found. Try another search term.")
else:
    df_display = df.rename(columns={
        'product_name': 'Product',
        'brands': 'Brand',
        'calories': 'Calories (kcal)',
        'fat': 'Fat (g)',
        'sugar': 'Sugar (g)',
        'protein': 'Proteins (g)',
        'calories_per_gram': 'Cal/gram'
    })
    
    st.success(f"✅ Found {len(df_display)} products for '{search}'")
    st.dataframe(
        df_display[['Product', 'Brand', 'Calories (kcal)', 'Fat (g)', 'Sugar (g)', 'Proteins (g)', 'Cal/gram']].head(10), 
        use_container_width=True, 
        height=400
    )

    df_clean = df_display.dropna(subset=["Calories (kcal)"])
    if not df_clean.empty:
        st.subheader("📊 Nutrition Stats")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Avg Calories", f"{df_clean['Calories (kcal)'].mean():.0f} kcal")
        col2.metric("Avg Fat", f"{df_clean['Fat (g)'].mean():.1f} g")
        col3.metric("Avg Sugar", f"{df_clean['Sugar (g)'].mean():.1f} g")
        col4.metric("Avg Protein", f"{df_clean['Proteins (g)'].mean():.1f} g")
        
        st.bar_chart(df_clean[["Calories (kcal)", "Fat (g)", "Sugar (g)", "Proteins (g)"]].mean())

st.markdown("---")
st.caption(f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")