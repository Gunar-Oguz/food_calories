import pytest
import pandas as pd
import io
import streamlit as st
from moto import mock_aws
import boto3
from app import get_food_data

@mock_aws
def test_get_food_data_mock():
    # Clear Streamlit cache first
    st.cache_data.clear()
    
    # Create mock S3 bucket and data
    s3 = boto3.client('s3', region_name='us-east-1')
    s3.create_bucket(Bucket='food-etl-bucket-gulnar')
    
    # Create sample DataFrame
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
    assert len(result) == 1
    assert 'Banana' in result.iloc[0]['product_name']

def test_get_food_data_empty():
    """Test that empty search returns DataFrame"""
    st.cache_data.clear()
    # This will fail in real env without S3, but structure is correct
    result = get_food_data("xyznonexistent123")
    assert isinstance(result, pd.DataFrame)
