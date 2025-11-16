import streamlit as st
import pandas as pd
import requests
import boto3
import io
from datetime import datetime

st.set_page_config(page_title="🥗 Nutrition & Food Insights", page_icon="🥗", layout="wide")
st.title("🥗 Nutrition & Food Insights Dashboard")
st.markdown("Learning automation & deployment using S3 processed data and public APIs.")

# Sidebar
st.sidebar.header("⚙️ Controls")
api_choice = st.sidebar.selectbox(
    "Choose Data Source",
    ["🍎 Open Food Facts (Foods)", "🌤️ Weather & Air Quality", "🌍 Countries Nutrition Index"]
)

if st.sidebar.button("🔄 Refresh", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("✅ Data from S3 (Processed)")

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_food_data(query="apple"):
    """Read processed food data from S3"""
    try:
        # Download from S3
        s3 = boto3.client('s3')
        obj = s3.get_object(Bucket='food-etl-bucket-gulnar', Key='write/processed_data.parquet')
        df = pd.read_parquet(io.BytesIO(obj['Body'].read()))
        
        # Filter by search term
        df_filtered = df[df['product_name'].str.contains(query, case=False, na=False)]
        
        return df_filtered
    except Exception as e:
        st.error(f"Error reading from S3: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=300)
def get_air_quality():
    r = requests.get("https://api.openaq.org/v2/latest?country=US&limit=50", timeout=10)
    r.raise_for_status()
    return r.json()["results"]

@st.cache_data(ttl=300)
def get_country_data():
    r = requests.get("https://restcountries.com/v3.1/all", timeout=10)
    r.raise_for_status()
    return r.json()

# --- MAIN CONTENT ---
with st.spinner(f"Fetching data from {api_choice}..."):

    # 1️⃣ Open Food Facts (FROM S3!)
    if api_choice.startswith("🍎"):
        search = st.text_input("Enter a food name:", "banana")
        df = get_food_data(search)
        
        if df.empty:
            st.warning("No data found.")
        else:
            # Rename columns to match display
            df_display = df.rename(columns={
                'product_name': 'Product',
                'brands': 'Brand',
                'calories': 'Calories (kcal)',
                'fat': 'Fat (g)',
                'sugar': 'Sugar (g)',
                'protein': 'Proteins (g)',
                'calories_per_gram': 'Cal/gram'
            })
            
            st.success(f"✅ Found {len(df_display)} products for '{search}' (from S3 processed data)")
            st.dataframe(df_display[['Product', 'Brand', 'Calories (kcal)', 'Fat (g)', 'Sugar (g)', 'Proteins (g)', 'Cal/gram']].head(10), 
                        use_container_width=True, height=400)

            df_clean = df_display.dropna(subset=["Calories (kcal)"])
            if not df_clean.empty:
                st.subheader("📊 Basic Nutrition Stats")
                st.metric("Avg Calories", f"{df_clean['Calories (kcal)'].mean():.0f} kcal")
                st.bar_chart(df_clean[["Calories (kcal)", "Fat (g)", "Sugar (g)", "Proteins (g)"]].mean())

    # 2️⃣ Air Quality
    elif api_choice.startswith("🌤️"):
        data = get_air_quality()
        df = pd.DataFrame([{
            "City": i["city"],
            "Parameter": i["measurements"][0]["parameter"],
            "Value": i["measurements"][0]["value"],
            "Unit": i["measurements"][0]["unit"]
        } for i in data])
        st.success(f"✅ Retrieved {len(df)} air quality records.")
        st.dataframe(df.head(10), use_container_width=True)
        st.subheader("🌫️ Average Pollution by Parameter")
        st.bar_chart(df.groupby("Parameter")["Value"].mean())

    # 3️⃣ Country Nutrition Index
    elif api_choice.startswith("🌍"):
        data = get_country_data()
        df = pd.DataFrame([{
            "Country": c.get("name", {}).get("common", "N/A"),
            "Region": c.get("region", "N/A"),
            "Population": c.get("population", 0),
            "Area": c.get("area", 0)
        } for c in data])
        df["Nutrition Index"] = (df["Population"] / (df["Area"] + 1)) % 100
        st.success("✅ Loaded country data and computed sample Nutrition Index")
        st.bar_chart(df.head(20).set_index("Country")["Nutrition Index"])

st.markdown("----")
st.caption(f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Food data from S3, other APIs public")