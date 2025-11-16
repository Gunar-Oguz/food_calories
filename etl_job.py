import boto3
import pandas as pd
import os

def extract():
    """EXTRACT: Download data from S3"""
    print("EXTRACT: Downloading data from S3...")
    
    s3 = boto3.client('s3')
    
    s3.download_file(
        'food-etl-bucket-gulnar',
        'read/food_data.parquet',
        'temp_input.parquet'
    )
    
    df = pd.read_parquet('temp_input.parquet')
    print(f"  ✅ Downloaded {len(df)} rows")
    
    return df

def transform(df):
    """TRANSFORM: Process the data"""
    print("TRANSFORM: Processing data...")
    
    # Add a new column: calories per gram
    df['calories_per_gram'] = df['calories'] / 100
    
    # Remove rows with missing calories
    df = df.dropna(subset=['calories'])
    
    print(f"  ✅ Transformed {len(df)} rows")
    
    return df

def load(df):
    """LOAD: Upload processed data to S3"""
    print("LOAD: Uploading to S3...")
    
    # Save as parquet locally first
    df.to_parquet('processed_data.parquet', index=False)
    
    # Upload to S3 write/ folder
    s3 = boto3.client('s3')
    s3.upload_file(
        'processed_data.parquet',
        'food-etl-bucket-gulnar',
        'write/processed_data.parquet'
    )
    
    print(f"  ✅ Uploaded {len(df)} rows to S3")

def main():
    """Run the ETL pipeline"""
    print("\n=== STARTING ETL JOB ===\n")
    
    # E - Extract
    df = extract()
    
    # T - Transform
    df = transform(df)
    
    # L - Load
    load(df)
    
    print("\n=== ETL JOB COMPLETE ===\n")

if __name__ == "__main__":
    main()
