"""Streamlit dashboard: search foods, build a plate, see what it takes to burn it off.

Reads data/write/processed_data.parquet, or S3 when S3_BUCKET is set (see storage.py).
All nutrition maths lives in nutrition.py; this file is only the user interface.
"""
import altair as alt
import pandas as pd
import streamlit as st

import nutrition as nu
import storage

NUTRISCORE_COLORS = {"a": "#038141", "b": "#85BB2F", "c": "#FECB02", "d": "#EE8100", "e": "#E63E11"}
NOVA_TEXT = {1: "Unprocessed or minimally processed", 2: "Processed culinary ingredient",
             3: "Processed food", 4: "Ultra-processed food"}
TABLE_COLS = {"product_name": "Product", "brands": "Brand", "category": "Category", "nutriscore": "Nutri-Score",
              "calories": "kcal / 100 g", "protein": "Protein (g)", "carbs": "Carbs (g)", "fat": "Fat (g)",
              "sugar": "Sugar (g)", "fiber": "Fiber (g)"}


@st.cache_data(ttl=300)
def load_processed_data():
    """Cached for 5 minutes so every search does not re-read the file."""
    df = storage.read_parquet(storage.PROCESSED_KEY)
    for col in nu.NUTRIENTS:  # older files may not have every nutrient column yet
        if col not in df.columns:
            df[col] = float("nan")
    for col in ["code", "category", "food_group", "nutriscore", "nova", "image_url", "serving_size"]:
        if col not in df.columns:
            df[col] = None
    # Every product needs a unique key for the plate, even if the API had no barcode.
    df["code"] = df["code"].fillna(pd.Series(df.index, index=df.index).map("row-{}".format)).astype(str)
    return df


def search_foods(df, query):
    """Case-insensitive search on product name and brand. regex=False so '(' or '+' in a query can't break it."""
    text = df["product_name"].fillna("") + " " + df["brands"].fillna("")
    return df[text.str.contains(query, case=False, na=False, regex=False)]


def get_food_data(query="apple"):
    try:
        return search_foods(load_processed_data(), query)
    except Exception as e:  # noqa: BLE001 -- UI boundary: show any read error instead of crashing the page
        st.error(f"Could not read the data: {e}")
        return pd.DataFrame()


def label(row):
    return f"{row['product_name']} · {row['brands']} ({row['calories']:.0f} kcal/100 g)"


def nutriscore_badge(grade):
    if not isinstance(grade, str) or grade not in NUTRISCORE_COLORS:
        return "Nutri-Score: not rated"
    color = NUTRISCORE_COLORS[grade]
    return (f"<span style='background:{color};color:white;padding:2px 10px;border-radius:6px;"
            f"font-weight:700'>Nutri-Score {grade.upper()}</span>")


def nutrient_table(amounts, targets):
    shown = nu.to_display_units(amounts)
    pct = nu.percent_of_target(amounts, targets)
    rows = [{"Nutrient": lbl, "Amount": shown[col], "Unit": unit, "% of your day": pct.get(col)}
            for col, (lbl, unit, _, _) in nu.NUTRIENTS.items() if pd.notna(shown[col])]
    return pd.DataFrame(rows)


def show_nutrient_table(amounts, targets):
    table = nutrient_table(amounts, targets)
    st.dataframe(
        table, hide_index=True, use_container_width=True, height=35 * (len(table) + 1) + 3,
        column_config={
            "Amount": st.column_config.NumberColumn(format="%.1f"),
            "% of your day": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        },
    )


def show_burn(kcal, weight):
    if not kcal or kcal <= 0:
        return
    steps = nu.steps_to_burn(kcal, weight)
    st.markdown(f"**🚶 To burn {kcal:.0f} kcal** you would walk about **{steps:,.0f} steps**, or:")
    table = nu.burn_table(kcal, weight)
    cols = st.columns(len(table))
    for col, row in zip(cols, table.itertuples()):
        col.metric(row.Activity, f"{row.Minutes:.0f} min")


def sidebar_profile():
    st.sidebar.header("👤 About you")
    st.sidebar.caption("Used for your calorie target and the exercise maths. Nothing is stored.")
    sex = st.sidebar.radio("Sex", ["female", "male"], horizontal=True)
    age = st.sidebar.number_input("Age", 15, 100, 30)
    height = st.sidebar.number_input("Height (cm)", 120, 230, 165)
    weight = st.sidebar.number_input("Weight (kg)", 35, 250, 65)
    level = st.sidebar.selectbox("Activity", list(nu.ACTIVITY_LEVELS), index=1)
    target = nu.daily_calorie_target(weight, height, age, sex, level)
    st.sidebar.metric("Your daily calorie target", f"{target:,.0f} kcal")
    st.sidebar.caption("Mifflin-St Jeor equation × activity factor. An estimate, not medical advice.")
    return weight, nu.daily_targets(target)


def add_to_plate(code, grams):
    st.session_state.plate.append({"code": code, "grams": float(grams)})
    st.session_state.plate_version += 1
    st.toast("Added to your plate 🍽️")


# ---------------- tabs ----------------

def tab_search(df, weight, targets):
    c1, c2 = st.columns([3, 2])
    query = c1.text_input("Search a food or brand", "banana")
    groups = sorted(g for g in df["food_group"].dropna().unique() if g)
    picked = c2.multiselect("Food group", groups)
    results = search_foods(df, query)
    if picked:
        results = results[results["food_group"].isin(picked)]
    if results.empty:
        st.warning("No products found. Try another word, for example 'oats' or 'salmon'.")
        return

    st.success(f"Found {len(results)} products")
    st.dataframe(results[list(TABLE_COLS)].rename(columns=TABLE_COLS).head(50), hide_index=True,
                 use_container_width=True, height=260)

    options = results.sort_values("calories")
    code = st.selectbox("See details for", options["code"], format_func=lambda c: label(df.set_index("code").loc[c]))
    product = df.set_index("code").loc[code]
    product["code"] = code

    st.divider()
    left, right = st.columns([1, 3])
    if isinstance(product["image_url"], str):
        left.image(product["image_url"], width=160)
    right.subheader(product["product_name"])
    right.caption(f"{product['brands']} · {product['category']} · serving: {product['serving_size'] or 'n/a'}")
    right.markdown(nutriscore_badge(product["nutriscore"]), unsafe_allow_html=True)
    if pd.notna(product["nova"]):
        right.caption(f"NOVA {int(product['nova'])}: {NOVA_TEXT[int(product['nova'])]}")

    grams = st.slider("Portion (grams)", 10, 500, 100, step=10)
    amounts = nu.scale(product, grams)
    show_nutrient_table(amounts, targets)
    show_burn(amounts["calories"], weight)
    st.button("➕ Add to my plate", on_click=add_to_plate, args=(code, grams), type="primary")

    swap = nu.healthier_swap(df.reset_index(drop=True), product)
    if swap is not None:
        st.info(f"💡 **Healthier swap:** {swap['product_name']} ({swap['brands']}): "
                f"Nutri-Score {str(swap['nutriscore'] or '?').upper()}, {swap['calories']:.0f} kcal/100 g "
                f"vs {product['calories']:.0f}.")


def tab_plate(df, weight, targets):
    plate = st.session_state.plate
    if not plate:
        st.info("Your plate is empty. Find a food in **🔍 Search**, choose a portion and press **➕ Add to my plate**.")
        return
    by_code = df.set_index("code")
    items = pd.DataFrame(plate)
    items["Food"] = items["code"].map(lambda c: label(by_code.loc[c]))
    items["Remove"] = False
    # The editor remembers edits by row position, so its key changes whenever rows are added or removed.
    edited = st.data_editor(
        items[["Food", "grams", "Remove"]].rename(columns={"grams": "Grams"}), hide_index=True,
        use_container_width=True, disabled=["Food"], key=f"plate_editor_{st.session_state.plate_version}",
        column_config={"Grams": st.column_config.NumberColumn(min_value=0, max_value=2000, step=10)},
    )
    items["grams"] = edited["Grams"].fillna(0).astype(float)
    st.session_state.plate = items[["code", "grams"]].to_dict("records")
    clear = st.button("🗑️ Clear plate")
    if clear or edited["Remove"].any():
        keep = pd.Series(not clear, index=items.index) & ~edited["Remove"]
        st.session_state.plate = items.loc[keep, ["code", "grams"]].to_dict("records")
        st.session_state.plate_version += 1
        st.rerun()

    foods = by_code.loc[items["code"]].reset_index(drop=True)
    totals = nu.plate_totals(foods, items["grams"])
    kcal = totals.get("calories") or 0

    st.subheader("Totals")
    m = st.columns(4)
    m[0].metric("Calories", f"{kcal:,.0f} kcal", f"{100 * kcal / targets['calories']:.0f}% of your day",
                delta_color="off")
    for col, name in zip(m[1:], ["protein", "carbs", "fat"]):
        col.metric(nu.NUTRIENTS[name][0], f"{totals.get(name) or 0:.1f} g")

    left, right = st.columns(2)
    with left:
        st.markdown("**Where the calories come from**")
        split = nu.macro_split(totals)
        st.bar_chart(pd.Series({nu.NUTRIENTS[k][0]: v for k, v in split.items()}, name="% of calories"),
                     horizontal=True)
    with right:
        st.markdown("**Share of your daily needs**")
        show_nutrient_table(totals, targets)
    show_burn(kcal, weight)


def tab_compare(df, targets):
    picks = st.multiselect("Choose 2 to 4 products", df["code"], max_selections=4,
                           format_func=lambda c: label(df.set_index("code").loc[c]))
    if len(picks) < 2:
        st.info("Pick at least two products to compare them per 100 g.")
        return
    chosen = df.set_index("code").loc[picks]
    names = chosen["product_name"].str.slice(0, 30)
    grams_cols = ["protein", "carbs", "sugar", "fiber", "fat", "saturated_fat", "salt"]
    chart = chosen[grams_cols].rename(columns={c: nu.NUTRIENTS[c][0] for c in grams_cols})
    chart.index = names
    st.markdown("**Grams per 100 g**")
    st.bar_chart(chart.T, stack=False)
    table = chosen[["calories", "nutriscore", "nova", *grams_cols]].copy()
    table.index = names
    st.dataframe(table.T, use_container_width=True)


def tab_explore(df):
    st.markdown(f"**{len(df)} products** in **{df['category'].nunique()} categories**")
    st.markdown("**Calories vs protein** (each dot is a product)")
    st.scatter_chart(df, x="calories", y="protein", color="food_group" if df["food_group"].notna().any() else None)

    left, right = st.columns(2)
    with left:
        st.markdown("**Most protein per 100 kcal**")
        best = df.assign(p=nu.protein_per_100_kcal(df)).dropna(subset=["p"]).nlargest(10, "p")
        st.dataframe(best[["product_name", "category", "p"]], hide_index=True, use_container_width=True,
                     column_config={"product_name": st.column_config.TextColumn("Product", width="medium"),
                                    "category": st.column_config.TextColumn("Category", width="small"),
                                    "p": st.column_config.NumberColumn("g protein / 100 kcal", format="%.1f")})
    with right:
        st.markdown("**Nutri-Score spread**")
        st.altair_chart(nutriscore_chart(df), use_container_width=True)

    st.markdown("**Average calories per 100 g by food group**")
    st.bar_chart(df.groupby("food_group")["calories"].mean().sort_values(), horizontal=True)


def nutriscore_chart(df):
    grades = [g.upper() for g in nu.NUTRISCORE_ORDER] + ["not rated"]
    counts = (df["nutriscore"].str.upper().fillna("not rated").value_counts()
              .reindex(grades, fill_value=0).rename_axis("grade").reset_index(name="products"))
    colors = [NUTRISCORE_COLORS[g] for g in nu.NUTRISCORE_ORDER] + ["#BBBBBB"]
    return alt.Chart(counts).mark_bar().encode(
        x=alt.X("grade:N", sort=grades, title=None, axis=alt.Axis(labelAngle=0)),
        y=alt.Y("products:Q", title="Products"),
        color=alt.Color("grade:N", scale=alt.Scale(domain=grades, range=colors), legend=None),
        tooltip=["grade", "products"],
    ).properties(height=320)


def tab_pipeline(df):
    fetched = df["fetched_at"].max() if "fetched_at" in df.columns else None
    c = st.columns(3)
    c[0].metric("Products", len(df))
    c[1].metric("Categories", df["category"].nunique())
    c[2].metric("Last refresh (UTC)", str(fetched)[:16].replace("T", " ") if fetched else "unknown")
    st.markdown("""
Every day at 10:00 UTC a GitHub Actions job runs the pipeline and commits fresh data; this app then redeploys.

1. **Fetch** (`fetch_data.py`): searches OpenFoodFacts for 33 foods, politely (rate limit, retries, backoff)
2. **Transform** (`etl_job.py`): removes missing or impossible values and duplicates, normalises scores
3. **Serve** (`app.py` + `nutrition.py`): this dashboard

Code, tests and CI/CD: [github.com/Gunar-Oguz/food_calories](https://github.com/Gunar-Oguz/food_calories)
""")
    st.markdown("**Data completeness** (share of products that have each nutrient)")
    present = df[list(nu.NUTRIENTS)].notna().mean().mul(100).rename(lambda c: nu.NUTRIENTS[c][0])
    st.bar_chart(present.rename("% of products"), horizontal=True)


def main():
    st.set_page_config(page_title="Food Calories", page_icon="🥗", layout="wide")
    st.session_state.setdefault("plate", [])
    st.session_state.setdefault("plate_version", 0)
    st.title("🥗 Food Calories & Nutrition")
    st.caption("Real products from the OpenFoodFacts API, cleaned by a daily ETL pipeline. "
               "Build a plate, check your daily needs, and see what it takes to burn it off.")

    weight, targets = sidebar_profile()
    try:
        df = load_processed_data()
    except Exception as e:  # noqa: BLE001 -- UI boundary: show any read error instead of crashing the page
        st.error(f"Could not read the data: {e}")
        return

    plate_label = f"🍽️ My plate ({len(st.session_state.plate)})"
    search, plate, compare, explore, pipeline = st.tabs(
        ["🔍 Search", plate_label, "⚖️ Compare", "📊 Explore", "⚙️ Pipeline"])
    with search:
        tab_search(df, weight, targets)
    with plate:
        tab_plate(df, weight, targets)
    with compare:
        tab_compare(df, targets)
    with explore:
        tab_explore(df)
    with pipeline:
        tab_pipeline(df)


if __name__ == "__main__":
    main()
