"""Where the pipeline keeps its files: S3 when S3_BUCKET is set, otherwise the local data/ folder.

Both use the same layout, so data/read/food_data.parquet locally is s3://<bucket>/read/food_data.parquet on AWS.
"""
import io
import os
from pathlib import Path

import boto3
import pandas as pd

RAW_KEY = "read/food_data.parquet"
PROCESSED_KEY = "write/processed_data.parquet"
LOCAL_DIR = Path(os.getenv("DATA_DIR", Path(__file__).parent / "data"))


def bucket():
    return os.getenv("S3_BUCKET")


def describe(key):
    return f"s3://{bucket()}/{key}" if bucket() else f"data/{key}"


def read_parquet(key):
    if bucket():
        obj = boto3.client("s3").get_object(Bucket=bucket(), Key=key)
        return pd.read_parquet(io.BytesIO(obj["Body"].read()))
    return pd.read_parquet(LOCAL_DIR / key)


def write_parquet(df, key):
    if bucket():
        buffer = io.BytesIO()
        df.to_parquet(buffer, index=False)
        boto3.client("s3").put_object(Bucket=bucket(), Key=key, Body=buffer.getvalue())
    else:
        path = LOCAL_DIR / key
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_parquet(path, index=False)
