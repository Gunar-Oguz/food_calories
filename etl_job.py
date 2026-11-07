"""ETL: read raw products (read/), clean them, write the result (write/). Storage is S3 or local, see storage.py."""
import storage

# Fat is the densest nutrient at about 9 kcal per gram, so 100 g of food can't exceed ~900 kcal.
MAX_KCAL_PER_100G = 900
# Nutrients measured in grams per 100 g can't be negative or above 100 g.
GRAM_COLS = ["protein", "carbs", "sugar", "fiber", "fat", "saturated_fat", "salt",
             "calcium", "iron", "potassium", "vitamin_c", "vitamin_d"]
NUTRISCORE_GRADES = {"a", "b", "c", "d", "e"}


def extract():
    """EXTRACT: load the raw products."""
    print(f"EXTRACT: Reading {storage.describe(storage.RAW_KEY)}")
    df = storage.read_parquet(storage.RAW_KEY)
    print(f"  ✅ Read {len(df)} rows")
    return df


def transform(df):
    """TRANSFORM: drop unnamed products and missing or impossible calories, blank out impossible nutrients,
    normalise scores, remove duplicates, add calories per gram, round."""
    print("TRANSFORM: Processing data...")
    before = len(df)
    df = df.dropna(subset=["calories"])
    df = df[df["product_name"].str.strip().ne("Unknown")]  # a product nobody can recognise is not useful
    df = df[df["calories"].between(0, MAX_KCAL_PER_100G)].copy()

    gram_cols = [c for c in GRAM_COLS if c in df.columns]
    df[gram_cols] = df[gram_cols].where(df[gram_cols].ge(0) & df[gram_cols].le(100))
    if "nutriscore" in df.columns:
        grade = df["nutriscore"].astype("string").str.lower()
        df["nutriscore"] = grade.where(grade.isin(NUTRISCORE_GRADES))
    if "nova" in df.columns:
        df["nova"] = df["nova"].where(df["nova"].between(1, 4))

    df = df.drop_duplicates(subset=["product_name", "brands"])
    if "code" in df.columns:
        df = df[~(df["code"].notna() & df["code"].duplicated())]
    df = df.assign(calories_per_gram=df["calories"] / 100).reset_index(drop=True)
    df = df.round({"calories": 1, "calories_per_gram": 3, **{c: 3 for c in gram_cols}})
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
