"""FETCH: pull nutrition facts from the OpenFoodFacts API and save them as raw data (read/)."""
import time
from datetime import UTC, datetime

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import storage

API_URL = "https://world.openfoodfacts.org/cgi/search.pl"

# Search term -> food group. Each term becomes the product's "category", used for swaps and charts.
FOODS = {
    "banana": "Fruits", "apple": "Fruits", "orange": "Fruits", "avocado": "Fruits", "strawberries": "Fruits",
    "broccoli": "Vegetables", "spinach": "Vegetables", "carrots": "Vegetables",
    "rice": "Grains", "oats": "Grains", "bread": "Grains", "pasta": "Grains", "quinoa": "Grains",
    "chicken breast": "Protein", "salmon": "Protein", "tuna": "Protein", "eggs": "Protein", "tofu": "Protein",
    "lentils": "Protein", "chickpeas": "Protein", "almonds": "Protein", "peanut butter": "Protein",
    "greek yogurt": "Dairy", "milk": "Dairy", "cheddar cheese": "Dairy",
    "dark chocolate": "Snacks & treats", "potato chips": "Snacks & treats", "cookies": "Snacks & treats",
    "ice cream": "Snacks & treats", "granola bar": "Snacks & treats", "pizza": "Snacks & treats",
    "orange juice": "Drinks", "cola": "Drinks",
}

# Our column name -> OpenFoodFacts nutriment key. Everything is per 100 g; minerals and vitamins arrive in grams.
NUTRIMENTS = {
    "calories": "energy-kcal_100g",
    "protein": "proteins_100g",
    "carbs": "carbohydrates_100g",
    "sugar": "sugars_100g",
    "fiber": "fiber_100g",
    "fat": "fat_100g",
    "saturated_fat": "saturated-fat_100g",
    "salt": "salt_100g",
    "calcium": "calcium_100g",
    "iron": "iron_100g",
    "potassium": "potassium_100g",
    "vitamin_c": "vitamin-c_100g",
    "vitamin_d": "vitamin-d_100g",
}
NUMERIC_COLS = list(NUTRIMENTS)
FIELDS = "code,product_name,brands,nutriscore_grade,nova_group,image_front_small_url,serving_size,nutriments"
COLUMNS = ["code", "product_name", "brands", "category", "food_group", "nutriscore", "nova", "image_url",
           "serving_size", *NUMERIC_COLS]


def parse_products(products, category="", food_group=""):
    """Turn raw API products into flat rows. Missing values become None."""
    rows = []
    for product in products:
        nutriments = product.get("nutriments", {})
        rows.append({
            "code": product.get("code"),
            "product_name": product.get("product_name") or "Unknown",
            "brands": product.get("brands") or "Unknown",
            "category": category,
            "food_group": food_group,
            "nutriscore": product.get("nutriscore_grade"),
            "nova": product.get("nova_group"),
            "image_url": product.get("image_front_small_url"),
            "serving_size": product.get("serving_size"),
            **{col: nutriments.get(key) for col, key in NUTRIMENTS.items()},
        })
    return rows


def make_session():
    """A session that retries busy-server errors (429/5xx) with growing waits: 2s, 4s, 8s, 16s, capped at 30s.

    The server's Retry-After header is ignored on purpose: one reply asking us to wait an hour once froze a run.
    """
    retry = Retry(total=4, backoff_factor=2, backoff_max=30, respect_retry_after_header=False,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "food-calories-portfolio/1.0 (github.com/Gunar-Oguz/food_calories)"
    return session


def fetch_food_data(foods=FOODS, page_size=20, session=None, pause=7, deadline_s=15 * 60):
    """Search the API for each food and return one DataFrame of products.

    `foods` maps a search term to its food group (a plain list also works).
    OpenFoodFacts allows about 10 searches a minute, so we pause between searches. If one food still fails,
    we skip it and keep the rest; only if every search fails do we raise, so old data is never replaced by nothing.
    After `deadline_s` seconds we stop searching and keep what we have, so one slow day can't hang the job.
    """
    if not isinstance(foods, dict):
        foods = {food: "" for food in foods}
    session = session or make_session()
    rows, failed = [], []
    start = time.monotonic()
    for i, (food, group) in enumerate(foods.items()):
        if time.monotonic() - start > deadline_s:
            skipped = list(foods)[i:]
            print(f"  ⏱️ Time limit reached, skipping {len(skipped)} foods: {', '.join(skipped)}")
            failed.extend(skipped)
            break
        if i:
            time.sleep(pause)
        print(f"  Searching for: {food}", flush=True)
        try:
            response = session.get(
                API_URL,
                params={"search_terms": food, "json": "true", "page_size": page_size, "fields": FIELDS},
                timeout=30,
            )
            response.raise_for_status()
            rows.extend(parse_products(response.json().get("products", []), food, group))
        except requests.RequestException as e:
            print(f"  ⚠️ Skipping {food}: {type(e).__name__}", flush=True)
            failed.append(food)

    if len(failed) == len(foods):
        raise RuntimeError("Every API search failed; keeping the previous data.")

    df = pd.DataFrame(rows, columns=COLUMNS)
    # The API sometimes returns numbers as strings, so force every nutrient to a number.
    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    df["nova"] = pd.to_numeric(df["nova"], errors="coerce")
    df["fetched_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    return df


def main():
    print("Fetching data from OpenFoodFacts API...")
    df = fetch_food_data()
    print(f"Fetched {len(df)} products")
    storage.write_parquet(df, storage.RAW_KEY)
    print(f"  ✅ Saved to {storage.describe(storage.RAW_KEY)}")


if __name__ == "__main__":
    main()
