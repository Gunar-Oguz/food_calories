import pytest
import streamlit as st
from unittest.mock import patch
from app import get_food_data, get_air_quality, get_country_data

# 1️⃣ Mock Open Food Facts API
@patch("app.requests.get")
def test_get_food_data_mock(mock_get):
    st.cache_data.clear()  # ✅ clear cache first
    mock_get.return_value.json.return_value = {"products": [{"product_name": "Banana", "brands": "Dole"}]}
    mock_get.return_value.raise_for_status = lambda: None
    data = get_food_data("banana")
    assert data[0]["product_name"] == "Banana"

# 2️⃣ Mock Air Quality API
@patch("app.requests.get")
def test_get_air_quality_mock(mock_get):
    mock_get.return_value.json.return_value = {"results": [{"city": "Seattle", "measurements": [{"parameter": "pm25", "value": 12, "unit": "µg/m³"}]}]}
    mock_get.return_value.raise_for_status = lambda: None
    data = get_air_quality()
    assert data[0]["city"] == "Seattle"

# 3️⃣ Mock Country Data API
@patch("app.requests.get")
def test_get_country_data_mock(mock_get):
    mock_get.return_value.json.return_value = [{"name": {"common": "USA"}, "region": "Americas"}]
    mock_get.return_value.raise_for_status = lambda: None
    data = get_country_data()
    assert data[0]["name"]["common"] == "USA"
