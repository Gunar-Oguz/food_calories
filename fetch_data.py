import requests
import pandas as pd
import boto3

def fetch_food_data():
    print("Fetching data from OpenFoodFacts API...")
    
    foods_to_search = ["banana", "apple", "chicken", "rice", "bread"]
    all_data = []
    
    for food in foods_to_search:
        print(f"  Searching for: {food}")
        url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={food}&json=true&page_size=10"
        response = requests.get(url, timeout=30)
        products = response.json()["products"]
        
        for product in products:
            all_data.append({
                'product_name': product.get('product_name', 'Unknown'),
                'brands': product.get('brands', 'Unknown'),
                'calories': product.get('nutriments', {}).get('energy-kcal_100g'),
                'fat': product.get('nutriments', {}).get('fat_100g'),
                'sugar': product.get('nutriments', {}).get('sugars_100g'),
                'protein': product.get('nutriments', {}).get('proteins_100g')
            })
    
    print(f"Fetched {len(all_data)} products!")
    return all_data

if __name__ == "__main__":
    # Fetch data from API
    data = fetch_food_data()
    df = pd.DataFrame(data)
    
    # Convert numeric columns to proper numbers
    numeric_cols = ['calories', 'fat', 'sugar', 'protein']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Save locally first
    df.to_parquet('food_data.parquet')
    print("Saved as food_data.parquet!")
    print(f"File contains {len(df)} rows")
    
    # NEW: Upload to S3
    print("Uploading to S3...")
    s3 = boto3.client('s3')
    s3.upload_file(
        'food_data.parquet',
        'food-etl-bucket-gulnar',
        'read/food_data.parquet'
    )
    print("  ✅ Uploaded to S3 read/ folder!")
