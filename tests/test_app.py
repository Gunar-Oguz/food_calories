import io

import boto3
import pandas as pd
import pytest
import streamlit as st
from moto import mock_aws

import app
import etl_job
import fetch_data
import storage

BUCKET = "food-etl-bucket-gulnar"


@pytest.fixture
def s3(monkeypatch):
    """A fake S3 (moto) with the project bucket, so tests never touch real AWS."""
    monkeypatch.setenv("S3_BUCKET", BUCKET)
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        st.cache_data.clear()
        yield client


@pytest.fixture(autouse=True)
def fake_aws_credentials(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("S3_BUCKET", raising=False)


def put_parquet(client, key, df):
    buffer = io.BytesIO()
    df.to_parquet(buffer, index=False)
    client.put_object(Bucket=BUCKET, Key=key, Body=buffer.getvalue())


def raw_products():
    return pd.DataFrame({
        "product_name": ["Banana Smoothie", "Apple Pie", "Apple Pie", "No Label", "Broken"],
        "brands": ["Dole", "Generic", "Generic", "X", "Y"],
        "calories": [89.0, 237.0, 237.0, None, 4000.0],
        "fat": [0.3, 10.5, 10.5, 1.0, 1.0],
        "sugar": [12.0, 20.0, 20.0, 1.0, 1.0],
        "protein": [1.1, 2.0, 2.0, 1.0, 1.0],
    })


# ---------- fetch ----------

def test_parse_products_handles_missing_fields():
    rows = fetch_data.parse_products([
        {"product_name": "Rice", "brands": "Uncle Ben", "nutriments": {"energy-kcal_100g": 130}},
        {"product_name": "", "nutriments": {}},
    ])
    assert rows[0]["calories"] == 130 and rows[0]["fat"] is None
    assert rows[1]["product_name"] == "Unknown" and rows[1]["brands"] == "Unknown"


def test_fetch_converts_nutrients_to_numbers():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"products": [{"product_name": "Bread", "nutriments": {"energy-kcal_100g": "265", "fat_100g": "n/a"}}]}

    class FakeSession:
        def get(self, *args, **kwargs):
            return FakeResponse()

    df = fetch_data.fetch_food_data(foods=["bread"], session=FakeSession(), pause=0)
    assert df.loc[0, "calories"] == 265.0
    assert pd.isna(df.loc[0, "fat"])


class FlakySession:
    """Fails for the foods it is told to fail, answers normally for the rest."""

    def __init__(self, bad):
        self.bad = bad

    def get(self, url, params, timeout):
        if params["search_terms"] in self.bad:
            raise fetch_data.requests.ConnectionError("503")
        response = type("R", (), {})()
        response.raise_for_status = lambda: None
        response.json = lambda: {"products": [{"product_name": params["search_terms"], "nutriments": {}}]}
        return response


def test_fetch_skips_a_failing_food_and_keeps_the_rest():
    df = fetch_data.fetch_food_data(foods=["rice", "bread"], session=FlakySession({"rice"}), pause=0)
    assert list(df["product_name"]) == ["bread"]


def test_fetch_raises_when_every_search_fails():
    with pytest.raises(RuntimeError):
        fetch_data.fetch_food_data(foods=["rice", "bread"], session=FlakySession({"rice", "bread"}), pause=0)


# ---------- transform ----------

def test_transform_cleans_and_adds_calories_per_gram():
    out = etl_job.transform(raw_products())
    assert list(out["product_name"]) == ["Banana Smoothie", "Apple Pie"]  # null, duplicate and 4000 kcal removed
    assert out.loc[0, "calories_per_gram"] == pytest.approx(0.89)


def test_transform_does_not_change_its_input():
    raw = raw_products()
    etl_job.transform(raw)
    assert "calories_per_gram" not in raw.columns


# ---------- full pipeline ----------

def test_pipeline_end_to_end_on_s3(s3):
    put_parquet(s3, storage.RAW_KEY, raw_products())
    etl_job.main()
    result = app.get_food_data("apple")
    assert len(result) == 1
    assert result.iloc[0]["calories_per_gram"] == pytest.approx(2.37)


def test_pipeline_end_to_end_on_local_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "LOCAL_DIR", tmp_path)
    storage.write_parquet(raw_products(), storage.RAW_KEY)
    etl_job.main()
    assert (tmp_path / "write" / "processed_data.parquet").exists()
    st.cache_data.clear()
    assert len(app.get_food_data("banana")) == 1


# ---------- app ----------

def test_search_is_case_insensitive_and_safe_with_symbols():
    df = pd.DataFrame({"product_name": ["Banana Bread", "Rice (white)", None]})
    assert len(app.search_foods(df, "BANANA")) == 1
    assert len(app.search_foods(df, "(white")) == 1  # would raise if treated as a regex


def test_app_reads_committed_data_without_aws():
    st.cache_data.clear()
    result = app.get_food_data("banana")
    assert not result.empty
    assert result["product_name"].str.contains("banana", case=False).all()


def test_app_returns_empty_frame_when_data_is_missing(s3):
    # The bucket exists but the ETL has not written anything yet.
    result = app.get_food_data("banana")
    assert isinstance(result, pd.DataFrame) and result.empty
