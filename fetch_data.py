"""FETCH: pull nutrition facts from the OpenFoodFacts API and upload them to S3 (read/)."""
import io
import os

import boto3
import pandas as pd
import requests

BUCKET = os.getenv("S3_BUCKET", "food-etl-bucket-gulnar")
RAW_KEY = "read/food_data.parquet"
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


def fetch_food_data(foods=FOODS, page_size=10):
    """Search the API for each food and return one DataFrame of products."""
    rows = []
    for food in foods:
        print(f"  Searching for: {food}")
        response = requests.get(
            API_URL,
            params={"search_terms": food, "json": "true", "page_size": page_size},
            headers={"User-Agent": "food-calories-portfolio/1.0"},
            timeout=30,
        )
        response.raise_for_status()
        rows.extend(parse_products(response.json().get("products", [])))

    df = pd.DataFrame(rows, columns=["product_name", "brands", *NUMERIC_COLS])
    # The API sometimes returns numbers as strings, so force every nutrient to a number.
    df[NUMERIC_COLS] = df[NUMERIC_COLS].apply(pd.to_numeric, errors="coerce")
    return df


def upload(df, bucket=BUCKET, key=RAW_KEY):
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())


def main():
    print("Fetching data from OpenFoodFacts API...")
    df = fetch_food_data()
    print(f"Fetched {len(df)} products")
    upload(df)
    print(f"  ✅ Uploaded to s3://{BUCKET}/{RAW_KEY}")


if __name__ == "__main__":
    main()
