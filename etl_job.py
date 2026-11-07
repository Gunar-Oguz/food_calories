"""ETL: read raw products from S3 (read/), clean them, write the result to S3 (write/)."""
import io
import os

import boto3
import pandas as pd

BUCKET = os.getenv("S3_BUCKET", "food-etl-bucket-gulnar")
RAW_KEY = "read/food_data.parquet"
PROCESSED_KEY = "write/processed_data.parquet"

# Fat is the densest nutrient at about 9 kcal per gram, so 100 g of food can't exceed ~900 kcal.
MAX_KCAL_PER_100G = 900


def extract(bucket=BUCKET, key=RAW_KEY):
    """EXTRACT: download the raw parquet file from S3."""
    print("EXTRACT: Downloading data from S3...")
    obj = boto3.client("s3").get_object(Bucket=bucket, Key=key)
    df = pd.read_parquet(io.BytesIO(obj["Body"].read()))
    print(f"  ✅ Downloaded {len(df)} rows")
    return df


def transform(df):
    """TRANSFORM: drop missing or impossible calories, remove duplicates, add calories per gram."""
    print("TRANSFORM: Processing data...")
    before = len(df)
    df = df.dropna(subset=["calories"])
    df = df[df["calories"].between(0, MAX_KCAL_PER_100G)]
    df = df.drop_duplicates(subset=["product_name", "brands"])
    df = df.assign(calories_per_gram=df["calories"] / 100).reset_index(drop=True)
    print(f"  ✅ Kept {len(df)} of {before} rows")
    return df


def load(df, bucket=BUCKET, key=PROCESSED_KEY):
    """LOAD: upload the processed parquet file to S3."""
    print("LOAD: Uploading to S3...")
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    boto3.client("s3").put_object(Bucket=bucket, Key=key, Body=buffer.getvalue())
    print(f"  ✅ Uploaded {len(df)} rows to s3://{bucket}/{key}")


def main():
    print("\n=== STARTING ETL JOB ===\n")
    load(transform(extract()))
    print("\n=== ETL JOB COMPLETE ===\n")


if __name__ == "__main__":
    main()
