# Food Calories & Nutrition Dashboard

A full-stack data pipeline that fetches nutrition data from OpenFoodFacts API, processes it through an ETL pipeline on AWS, and displays it in an interactive Streamlit dashboard.

**[Live Demo](http://54.85.148.60:8501)** ← Try it now

---

## What It Does

Users can search for any food and instantly see:
- Calories per 100g
- Fat, sugar, and protein content
- Average nutrition stats with visualizations

The app also includes Air Quality data and Country Nutrition Index features to demonstrate working with multiple APIs.

---

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  OpenFoodFacts  │────▶│    AWS S3       │────▶│   Streamlit     │
│      API        │     │  (read/write)   │     │   Dashboard     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                        ┌──────┴──────┐
                        │  ETL Job    │
                        │  (Python)   │
                        └─────────────┘
```

**Data Flow:**
1. `fetch_data.py` pulls food data from OpenFoodFacts API → saves to S3 `read/` folder
2. `etl_job.py` extracts from S3, transforms (calculates calories/gram, removes nulls), loads to S3 `write/` folder
3. `app.py` reads processed data from S3 and displays in Streamlit

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit |
| Data Processing | pandas, parquet |
| Cloud Storage | AWS S3 |
| Deployment | AWS EC2 |
| Containerization | Docker |
| CI/CD | GitHub Actions |
| Testing | pytest |
| Data Source | OpenFoodFacts API |

---

## Project Structure

```
food_calories/
├── app.py                 # Streamlit dashboard
├── fetch_data.py          # Pulls data from OpenFoodFacts API
├── etl_job.py             # ETL pipeline (Extract → Transform → Load)
├── tests/
│   └── test_app.py        # Unit tests
├── Dockerfile             # Main app container
├── Dockerfile.etl         # ETL job container
├── Dockerfile.fetch       # Data fetch container
├── .github/
│   └── workflows/
│       └── release.yaml   # CI/CD pipeline
└── requirements.txt
```

---

## Run Locally

**Prerequisites:** Python 3.11+, AWS credentials configured

```bash
# Clone the repo
git clone https://github.com/Gunar-Oguz/food_calories.git
cd food_calories

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

---

## Run with Docker

```bash
# Build the image
docker build -t food-calories-app .

# Run the container
docker run -p 8501:8501 food-calories-app
```

Then open `http://localhost:8501`

---

## Run the ETL Pipeline

```bash
# Fetch fresh data from API
python fetch_data.py

# Run ETL job
python etl_job.py
```

---

## CI/CD Pipeline

The GitHub Actions workflow (`release.yaml`) automatically:
1. Runs tests with pytest
2. Builds Docker images
3. Pushes to Docker Hub

Triggered on every push to `main`.

---

## What I Learned

Building this project taught me:
- Designing ETL pipelines with clear Extract → Transform → Load separation
- Working with AWS S3 for cloud data storage
- Containerizing Python apps with Docker
- Setting up CI/CD with GitHub Actions
- Building interactive dashboards with Streamlit

---

## Author

**Gulnar Albushova**  
UC Berkeley Master's in Data Science (MIDS)  
[LinkedIn](https://www.linkedin.com/in/gulnar-albushova-253252140/) • [GitHub](https://github.com/Gunar-Oguz)