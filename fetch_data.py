"""FETCH: pull nutrition facts from the OpenFoodFacts API and save them as raw data (read/)."""
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import storage

API_URL = "https://world.openfoodfacts.org/cgi/search.pl"
FOODS = ["banana", "apple", "chicken", "rice", "bread"]
NUMERIC_COLS = ["calories", "fat", "sugar", "protein"]


def parse_products(products):
    """Turn raw API products into flat rows. Missing nutrients become None."""
    rows = []
    for product in products:
        nutriments = product.get("nutriments", {})
        rows.append({
            "product_name": product.get("product_name") or "Unknown",
            "brands": product.get("brands") or "Unknown",
            "calories": nutriments.get("energy-kcal_100g"),
            "fat": nutriments.get("fat_100g"),
            "sugar": nutriments.get("sugars_100g"),
            "protein": nutriments.get("proteins_100g"),
        })
    return rows


def make_session():
    """A session that retries busy-server errors (429/5xx) with growing waits: 2s, 4s, 8s, 16s, 32s."""
    retry = Retry(total=5, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "food-calories-portfolio/1.0 (github.com/Gunar-Oguz/food_calories)"
    return session


def fetch_food_data(foods=FOODS, page_size=10, session=None, pause=7):
    """Search the API for each food and return one DataFrame of products.

    OpenFoodFacts allows about 10 searches a minute, so we pause between searches. If one food still fails,
    we skip it and keep the rest; only if every search fails do we raise, so old data is never replaced by nothing.
    """
    session = session or make_session()
    rows, failed = [], []
    for i, food in enumerate(foods):
        if i:
            time.sleep(pause)
        print(f"  Searching for: {food}")
        try:
            response = session.get(
                API_URL,
                params={"search_terms": food, "json": "true", "page_size": page_size},
                timeout=30,
            )
            response.raise_for_status()
            rows.extend(parse_products(response.json().get("products", [])))
        except requests.RequestException as e:
            print(f"  ⚠️ Skipping {food}: {e}")
            failed.append(food)

    if len(failed) == len(foods):
        raise RuntimeError("Every API search failed; keeping the previous data.")

    df = pd.DataFrame(rows, columns=["product_name", "brands", *NUMERIC_COLS])
    # The API sometimes returns numbers as strings, so force every nutrient to a number.
    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    return df


def main():
    print("Fetching data from OpenFoodFacts API...")
    df = fetch_food_data()
    print(f"Fetched {len(df)} products")
    storage.write_parquet(df, storage.RAW_KEY)
    print(f"  ✅ Saved to {storage.describe(storage.RAW_KEY)}")


if __name__ == "__main__":
    main()
