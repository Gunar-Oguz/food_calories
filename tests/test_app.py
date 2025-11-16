import pytest
import pandas as pd
import io
import streamlit as st
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3
from app import get_food_data, get_air_quality, get_country_data

# 1️⃣ Mock S3 for get_food_data
@mock_aws
def test_get_food_data_mock():
    # Clear Streamlit cache first!
    st.cache_data.clear()
    
    # Create mock S3 bucket and data
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='food-etl-bucket-gulnar')
    
    # Create sample DataFrame (simulates your processed S3 data)
    sample_data = pd.DataFrame({
        'product_name': ['Banana Smoothie', 'Apple Pie', 'Orange Juice'],
        'brands': ['Dole', 'Generic', 'Tropicana'],
        'calories': [89.0, 237.0, 45.0],
        'fat': [0.3, 10.5, 0.1],
        'sugar': [12.0, 20.0, 9.0],
        'protein': [1.1, 2.0, 0.7],
        'calories_per_gram': [0.89, 2.37, 0.45]
    })
    
    # Upload to mock S3
    parquet_buffer = io.BytesIO()
    sample_data.to_parquet(parquet_buffer, index=False)
    parquet_buffer.seek(0)
    s3.put_object(
        Bucket='food-etl-bucket-gulnar',
        Key='write/processed_data.parquet',
        Body=parquet_buffer.getvalue()
    )
    
    # Test the function
    result = get_food_data("banana")
    
    # Assertions
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1  # Only "Banana Smoothie" matches
    assert 'Banana' in result.iloc[0]['product_name']

# 2️⃣ Mock Air Quality API
@patch("app.requests.get")
def test_get_air_quality_mock(mock_get):
    mock_get.return_value.json.return_value = {
        "results": [{
            "city": "Seattle",
            "measurements": [{"parameter": "pm25", "value": 12, "unit": "µg/m³"}]
        }]
    }
    mock_get.return_value.raise_for_status = lambda: None
    data = get_air_quality()
    assert data[0]["city"] == "Seattle"

# 3️⃣ Mock Country Data API
@patch("app.requests.get")
def test_get_country_data_mock(mock_get):
    mock_get.return_value.json.return_value = [
        {"name": {"common": "USA"}, "region": "Americas"}
    ]
    mock_get.return_value.raise_for_status = lambda: None
    data = get_country_data()
    assert data[0]["name"]["common"] == "USA"
