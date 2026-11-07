"""ETL: read raw products (read/), clean them, write the result (write/). Storage is S3 or local, see storage.py."""
import storage

# Fat is the densest nutrient at about 9 kcal per gram, so 100 g of food can't exceed ~900 kcal.
MAX_KCAL_PER_100G = 900


def extract():
    """EXTRACT: load the raw products."""
    print(f"EXTRACT: Reading {storage.describe(storage.RAW_KEY)}")
    df = storage.read_parquet(storage.RAW_KEY)
    print(f"  ✅ Read {len(df)} rows")
    return df


def transform(df):
    """TRANSFORM: drop missing or impossible calories, remove duplicates, add calories per gram, round."""
    print("TRANSFORM: Processing data...")
    before = len(df)
    df = df.dropna(subset=["calories"])
    df = df[df["calories"].between(0, MAX_KCAL_PER_100G)]
    df = df.drop_duplicates(subset=["product_name", "brands"])
    df = df.assign(calories_per_gram=df["calories"] / 100).reset_index(drop=True)
    df = df.round({"calories": 1, "fat": 2, "sugar": 2, "protein": 2, "calories_per_gram": 3})
    print(f"  ✅ Kept {len(df)} of {before} rows")
    return df


def load(df):
    """LOAD: save the processed products."""
    storage.write_parquet(df, storage.PROCESSED_KEY)
    print(f"LOAD: ✅ Wrote {len(df)} rows to {storage.describe(storage.PROCESSED_KEY)}")


def main():
    print("\n=== STARTING ETL JOB ===\n")
    load(transform(extract()))
    print("\n=== ETL JOB COMPLETE ===\n")


if __name__ == "__main__":
    main()
