"""Nutrition maths used by the dashboard. Pure functions only (no Streamlit, no I/O), so all of it is unit-tested.

Sources
- Daily Values: U.S. FDA, "Daily Value on the Nutrition and Supplement Facts Labels" (2,000 kcal reference diet).
- Calorie needs: Mifflin-St Jeor equation (Mifflin et al., 1990) times a standard activity factor.
- Exercise: MET values from the 2024 Adult Compendium of Physical Activities (pacompendium.com);
  kcal/min = MET x 3.5 x kg / 200.
- Steps: about 100 steps per minute is the cadence of moderate-intensity (brisk) walking (Tudor-Locke et al., 2018).
"""
import pandas as pd

# column -> (label, unit shown, factor from the stored grams to that unit, FDA Daily Value in that unit or None)
NUTRIENTS = {
    "calories":      ("Calories",      "kcal", 1,         2000),
    "protein":       ("Protein",       "g",    1,         50),
    "carbs":         ("Carbohydrates", "g",    1,         275),
    "sugar":         ("Sugars",        "g",    1,         50),  # FDA's 50 g is for added sugars; used as a guide
    "fiber":         ("Fiber",         "g",    1,         28),
    "fat":           ("Fat",           "g",    1,         78),
    "saturated_fat": ("Saturated fat", "g",    1,         20),
    "salt":          ("Salt",          "g",    1,         5.75),  # 2,300 mg sodium x 2.5 = 5.75 g salt
    "calcium":       ("Calcium",       "mg",   1000,      1300),
    "iron":          ("Iron",          "mg",   1000,      18),
    "potassium":     ("Potassium",     "mg",   1000,      4700),
    "vitamin_c":     ("Vitamin C",     "mg",   1000,      90),
    "vitamin_d":     ("Vitamin D",     "µg",   1_000_000, 20),
}
MACROS = ["protein", "carbs", "fat"]
KCAL_PER_GRAM = {"protein": 4, "carbs": 4, "fat": 9}

ACTIVITIES = {  # name -> MET, 2024 Adult Compendium (activity code in brackets)
    "Brisk walking (3.5 mph)": 4.8,  # [17200] walking, 3.5-3.9 mph, level, brisk
    "Running (6 mph)": 9.3,          # [12050] running, 6-6.3 mph (10 min/mile)
    "Cycling (12-14 mph)": 8.0,      # [01030] bicycling, 12-13.9 mph, leisure, moderate
    "Swimming (slow laps)": 5.8,     # [18240] swimming laps, freestyle, slow, recreational
}
WALKING = "Brisk walking (3.5 mph)"
STEPS_PER_MINUTE = 100

ACTIVITY_LEVELS = {
    "Sedentary (little exercise)": 1.2,
    "Light (1-3 days/week)": 1.375,
    "Moderate (3-5 days/week)": 1.55,
    "Active (6-7 days/week)": 1.725,
    "Very active (hard daily training)": 1.9,
}
NUTRISCORE_ORDER = ["a", "b", "c", "d", "e"]


def scale(per_100g, grams):
    """Nutrient amounts for `grams` of a food, given its values per 100 g (a Series or dict)."""
    return pd.Series(per_100g, dtype="float64").reindex(list(NUTRIENTS)) * grams / 100


def plate_totals(foods, grams):
    """Total nutrients for a plate. `foods` has one row per food (per-100 g values); `grams` lines up with it.

    A nutrient missing for one food counts as 0 in the sum, so a total is a lower bound when data is incomplete.
    """
    per_100g = foods.reindex(columns=list(NUTRIENTS)).astype("float64")
    weights = pd.Series(list(grams), index=foods.index, dtype="float64") / 100
    return per_100g.mul(weights, axis=0).sum(min_count=1)


def macro_split(totals):
    """Share of calories from protein, carbs and fat, in percent (adds up to 100)."""
    kcal = {m: (totals.get(m) or 0) * KCAL_PER_GRAM[m] for m in MACROS}
    total = sum(kcal.values())
    return {m: (100 * v / total if total else 0.0) for m, v in kcal.items()}


def kcal_per_minute(met, weight_kg):
    return met * 3.5 * weight_kg / 200


def minutes_to_burn(kcal, weight_kg, met):
    """Minutes of an activity needed to burn `kcal` for a person of `weight_kg`."""
    if weight_kg <= 0:
        raise ValueError("weight must be positive")
    return kcal / kcal_per_minute(met, weight_kg)


def burn_table(kcal, weight_kg):
    """Minutes for every activity, plus the matching walking steps."""
    rows = [{"Activity": name, "Minutes": minutes_to_burn(kcal, weight_kg, met)} for name, met in ACTIVITIES.items()]
    return pd.DataFrame(rows)


def steps_to_burn(kcal, weight_kg):
    return minutes_to_burn(kcal, weight_kg, ACTIVITIES[WALKING]) * STEPS_PER_MINUTE


def bmr_mifflin_st_jeor(weight_kg, height_cm, age, sex):
    """Resting calories per day. sex is 'female' or 'male'."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + (5 if sex == "male" else -161)


def daily_calorie_target(weight_kg, height_cm, age, sex, activity_level):
    return bmr_mifflin_st_jeor(weight_kg, height_cm, age, sex) * ACTIVITY_LEVELS[activity_level]


def daily_targets(calorie_target):
    """Daily Values in display units, with calories and the energy-based nutrients scaled to the person.

    FDA Daily Values assume 2,000 kcal; protein, carbs, sugar, fiber, fat and saturated fat scale with energy.
    Salt and the micronutrients do not.
    """
    ratio = calorie_target / 2000
    energy_based = {"calories", "protein", "carbs", "sugar", "fiber", "fat", "saturated_fat"}
    return {col: dv * ratio if col in energy_based else dv for col, (_, _, _, dv) in NUTRIENTS.items()}


def to_display_units(amounts):
    """Stored grams -> the unit shown to people (mg, µg for micronutrients)."""
    return pd.Series({col: amounts.get(col) * NUTRIENTS[col][2] if pd.notna(amounts.get(col)) else None
                      for col in NUTRIENTS}, dtype="float64")


def percent_of_target(amounts, targets):
    shown = to_display_units(amounts)
    return pd.Series({col: 100 * shown[col] / targets[col] for col in NUTRIENTS if pd.notna(shown[col])})


def protein_per_100_kcal(df):
    return (df["protein"] / df["calories"].where(df["calories"] > 0) * 100).round(1)


def healthier_swap(df, product):
    """A product from the same category with a better Nutri-Score, or the same score and at least 10% fewer
    calories. Returns the best one (best score, then fewest calories), or None."""
    same = df[(df["category"] == product["category"]) & (df["code"] != product["code"])]
    rank = {g: i for i, g in enumerate(NUTRISCORE_ORDER)}
    mine = rank.get(product.get("nutriscore"), len(rank))
    same = same.assign(_rank=same["nutriscore"].map(rank).fillna(len(rank)))
    better = same[(same["_rank"] < mine) | ((same["_rank"] == mine) & (same["calories"] <= 0.9 * product["calories"]))]
    if better.empty:
        return None
    return better.sort_values(["_rank", "calories"]).iloc[0].drop("_rank")
