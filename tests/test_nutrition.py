import pandas as pd
import pytest

import nutrition as nu


def test_scale_to_portion():
    amounts = nu.scale({"calories": 200, "protein": 10}, grams=150)
    assert amounts["calories"] == 300
    assert amounts["protein"] == 15
    assert pd.isna(amounts["fiber"])  # unknown stays unknown, not 0


def test_plate_totals_adds_foods_by_weight():
    foods = pd.DataFrame({"calories": [100, 400], "protein": [10, None]})
    totals = nu.plate_totals(foods, grams=[200, 50])
    assert totals["calories"] == 200 + 200
    assert totals["protein"] == 20  # the missing value counts as 0
    assert pd.isna(totals["fiber"])  # no food has fiber data at all


def test_macro_split_uses_4_4_9_kcal_per_gram():
    split = nu.macro_split({"protein": 25, "carbs": 25, "fat": 0})
    assert split == {"protein": 50, "carbs": 50, "fat": 0}
    split = nu.macro_split({"protein": 0, "carbs": 9, "fat": 4})  # 36 kcal each
    assert split["carbs"] == pytest.approx(50) and split["fat"] == pytest.approx(50)
    assert sum(nu.macro_split({"protein": 0, "carbs": 0, "fat": 0}).values()) == 0


def test_met_formula():
    # 70 kg brisk walking (4.8 MET): 4.8 * 3.5 * 70 / 200 = 5.88 kcal/min, so 100 kcal is 17.0 minutes
    assert nu.minutes_to_burn(100, 70, 4.8) == pytest.approx(17.0, abs=0.05)
    # a heavier person burns the same calories faster
    assert nu.minutes_to_burn(100, 90, 4.8) < nu.minutes_to_burn(100, 60, 4.8)
    with pytest.raises(ValueError):
        nu.minutes_to_burn(100, 0, 4.8)


def test_steps_follow_walking_minutes():
    minutes = nu.minutes_to_burn(250, 65, nu.ACTIVITIES[nu.WALKING])
    assert nu.steps_to_burn(250, 65) == pytest.approx(minutes * 100)


def test_burn_table_has_every_activity():
    table = nu.burn_table(300, 70)
    assert list(table["Activity"]) == list(nu.ACTIVITIES)
    assert table.set_index("Activity")["Minutes"].idxmin() == "Running (6 mph)"


def test_mifflin_st_jeor_known_values():
    # 70 kg, 175 cm, 30 years: 700 + 1093.75 - 150 = 1643.75, +5 male / -161 female
    assert nu.bmr_mifflin_st_jeor(70, 175, 30, "male") == pytest.approx(1648.75)
    assert nu.bmr_mifflin_st_jeor(70, 175, 30, "female") == pytest.approx(1482.75)
    sedentary = nu.daily_calorie_target(70, 175, 30, "male", "Sedentary (little exercise)")
    assert sedentary == pytest.approx(1648.75 * 1.2)


def test_daily_targets_scale_energy_nutrients_only():
    targets = nu.daily_targets(3000)
    assert targets["calories"] == 3000
    assert targets["fat"] == pytest.approx(78 * 1.5)
    assert targets["salt"] == 5.75  # salt does not grow with calories
    assert targets["vitamin_c"] == 90


def test_percent_of_target_converts_units():
    # 0.045 g vitamin C = 45 mg = 50% of the 90 mg Daily Value
    pct = nu.percent_of_target({"vitamin_c": 0.045, "calories": 500}, nu.daily_targets(2000))
    assert pct["vitamin_c"] == pytest.approx(50)
    assert pct["calories"] == pytest.approx(25)
    assert "iron" not in pct  # unknown nutrients are left out


def test_protein_per_100_kcal_skips_zero_calories():
    df = pd.DataFrame({"protein": [20, 5], "calories": [100, 0]})
    out = nu.protein_per_100_kcal(df)
    assert out[0] == 20 and pd.isna(out[1])


def products():
    return pd.DataFrame({
        "code": ["1", "2", "3", "4"],
        "category": ["cookies", "cookies", "cookies", "milk"],
        "nutriscore": ["e", "d", "e", "a"],
        "calories": [500, 450, 400, 40],
    })


def test_swap_prefers_better_nutriscore_then_fewer_calories():
    df = products()
    swap = nu.healthier_swap(df, df.iloc[0])
    assert swap["code"] == "2"  # grade d beats e, even though product 3 has fewer calories


def test_swap_same_grade_needs_10_percent_fewer_calories():
    df = products()[lambda d: d["code"] != "2"]
    assert nu.healthier_swap(df, df.iloc[0])["code"] == "3"  # 400 <= 0.9 * 500


def test_swap_stays_in_category_and_can_be_none():
    df = products()
    assert nu.healthier_swap(df, df.iloc[3]) is None  # milk has no other milk to swap to
