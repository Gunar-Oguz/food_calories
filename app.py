from health_check import start_health_server
import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- API FUNCTIONS ---
@st.cache_data(ttl=300)
def get_food_data(query="apple"):
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&json=true&page_size=50"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()["products"]

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

def main():
    start_health_server()
    st.set_page_config(page_title="🥗 Nutrition & Food Insights", page_icon="🥗", layout="wide")
    st.title("🥗 Nutrition & Food Insights Dashboard")
    st.markdown("Learning automation & deployment using public, free APIs (no keys needed).")

    # Sidebar
    st.sidebar.header("⚙️ Controls")
    api_choice = st.sidebar.selectbox(
        "Choose Data Source",
        ["🍎 Open Food Facts (Foods)", "🌤️ Weather & Air Quality", "🌍 Countries Nutrition Index"]
    )

    if st.sidebar.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("✅ No API key needed")

    # --- MAIN CONTENT ---
    with st.spinner(f"Fetching data from {api_choice}..."):

        # 1️⃣ Open Food Facts
        if api_choice.startswith("🍎"):
            search = st.text_input("Enter a food name:", "banana")
            data = get_food_data(search)
            if not data:
                st.warning("No data found.")
            else:
                df = pd.DataFrame([{
                    "Product": i.get("product_name", "N/A"),
                    "Brand": i.get("brands", "N/A"),
                    "Calories (kcal)": i.get("nutriments", {}).get("energy-kcal_100g"),
                    "Fat (g)": i.get("nutriments", {}).get("fat_100g"),
                    "Sugar (g)": i.get("nutriments", {}).get("sugars_100g"),
                    "Proteins (g)": i.get("nutriments", {}).get("proteins_100g")
                } for i in data if "nutriments" in i])
                st.success(f"✅ Found {len(df)} products for '{search}'")
                st.dataframe(df.head(10), use_container_width=True, height=400)

                # Simple wrangling
                df_clean = df.dropna(subset=["Calories (kcal)"])
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

        # 3️⃣ Country Nutrition Index (fictional aggregate)
        elif api_choice.startswith("🌍"):
            data = get_country_data()
            df = pd.DataFrame([{
                "Country": c.get("name", {}).get("common", "N/A"),
                "Region": c.get("region", "N/A"),
                "Population": c.get("population", 0),
                "Area": c.get("area", 0)
            } for c in data])
            df["Nutrition Index"] = (df["Population"] / (df["Area"] + 1)) % 100  # mock calc
            st.success("✅ Loaded country data and computed sample Nutrition Index")
            st.bar_chart(df.head(20).set_index("Country")["Nutrition Index"])

    st.markdown("----")
    st.caption(f"🕒 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | All APIs are public, no signup required.")

main()
