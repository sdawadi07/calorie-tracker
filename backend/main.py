import os
from datetime import datetime

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# DEMO_KEY works out of the box but is rate-limited (30 req/hour, 50/day).
# Get a free personal key at https://api.data.gov/signup/ and set USDA_API_KEY
# as an environment variable if you hit the limit.
USDA_API_KEY = os.environ.get("USDA_API_KEY", "DEMO_KEY")
USDA_SEARCH_URL = "https://api.nal.usda.gov/fdc/v1/foods/search"

NUTRIENT_NAME_MAP = {
    "Energy": "calories_per_100g",
    "Protein": "protein_per_100g",
    "Carbohydrate, by difference": "carbs_per_100g",
    "Total lipid (fat)": "fat_per_100g",
}


@app.get("/foods/search", response_model=list[schemas.USDAFoodResult])
def search_usda_foods(q: str):
    # USDA's API is occasionally flaky (intermittent 404s on valid requests),
    # so retry a couple times before giving up. Rate limiting (429) won't be
    # fixed by retrying, so fail fast on that one.
    resp = None
    for _ in range(3):
        resp = requests.get(
            USDA_SEARCH_URL,
            params={"query": q, "api_key": USDA_API_KEY, "pageSize": 15},
            timeout=10,
        )
        if resp.status_code == 200 or resp.status_code == 429:
            break

    if resp is not None and resp.status_code == 429:
        raise HTTPException(
            status_code=429,
            detail=(
                "USDA API rate limit reached. Get a free personal key at "
                "https://api.data.gov/signup/ and set it as the USDA_API_KEY "
                "environment variable."
            ),
        )
    if resp is None or resp.status_code != 200:
        raise HTTPException(status_code=502, detail="USDA food lookup failed")

    results = []
    for item in resp.json().get("foods", []):
        values = {"calories_per_100g": None, "protein_per_100g": 0, "carbs_per_100g": 0, "fat_per_100g": 0}
        for nutrient in item.get("foodNutrients", []):
            field = NUTRIENT_NAME_MAP.get(nutrient.get("nutrientName"))
            if field:
                values[field] = nutrient.get("value", 0)
        if values["calories_per_100g"] is None:
            continue
        results.append({"name": item["description"], **values})
    return results


@app.post("/foods/", response_model=schemas.FoodOut)
def create_food(food: schemas.FoodCreate, db: Session = Depends(get_db)):
    db_food = models.Food(**food.model_dump())
    db.add(db_food)
    db.commit()
    db.refresh(db_food)
    return db_food


@app.get("/foods/", response_model=list[schemas.FoodOut])
def list_foods(db: Session = Depends(get_db)):
    return db.query(models.Food).all()


@app.post("/log/", response_model=schemas.LogEntryOut)
def create_log_entry(entry: schemas.LogEntryCreate, db: Session = Depends(get_db)):
    food = db.query(models.Food).filter(models.Food.id == entry.food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    db_entry = models.LogEntry(food_id=entry.food_id, grams=entry.grams)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.post("/log/quick", response_model=schemas.LogEntryOut)
def create_quick_log_entry(entry: schemas.QuickLogCreate, db: Session = Depends(get_db)):
    """Log food by name + total calories, without tracking per-100g/grams separately."""
    db_food = models.Food(name=entry.name, calories_per_100g=entry.calories)
    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    db_entry = models.LogEntry(food_id=db_food.id, grams=100)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.post("/log/from_search", response_model=schemas.LogEntryOut)
def create_log_entry_from_search(entry: schemas.LogFromSearchCreate, db: Session = Depends(get_db)):
    db_food = models.Food(
        name=entry.name,
        calories_per_100g=entry.calories_per_100g,
        protein_per_100g=entry.protein_per_100g,
        carbs_per_100g=entry.carbs_per_100g,
        fat_per_100g=entry.fat_per_100g,
    )
    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    db_entry = models.LogEntry(food_id=db_food.id, grams=entry.grams)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.delete("/log/{entry_id}", status_code=204)
def delete_log_entry(entry_id: int, db: Session = Depends(get_db)):
    db_entry = db.query(models.LogEntry).filter(models.LogEntry.id == entry_id).first()
    if not db_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(db_entry)
    db.commit()


@app.get("/log/today", response_model=list[schemas.LogEntryOut])
def get_today_log(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    return (
        db.query(models.LogEntry)
        .filter(func.date(models.LogEntry.logged_at) == today)
        .all()
    )


@app.get("/log/today/total")
def get_today_total(db: Session = Depends(get_db)):
    today = datetime.utcnow().date()
    entries = (
        db.query(models.LogEntry)
        .filter(func.date(models.LogEntry.logged_at) == today)
        .all()
    )
    total = sum(e.food.calories_per_100g * e.grams / 100 for e in entries)
    return {"date": str(today), "total_calories": round(total, 1)}


@app.post("/weight/", response_model=schemas.WeightEntryOut)
def log_weight(entry: schemas.WeightEntryCreate, db: Session = Depends(get_db)):
    db_entry = models.WeightEntry(weight_kg=entry.weight_kg)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/weight/", response_model=list[schemas.WeightEntryOut])
def list_weight(db: Session = Depends(get_db)):
    return (
        db.query(models.WeightEntry)
        .order_by(models.WeightEntry.recorded_at.desc())
        .all()
    )
