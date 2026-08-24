from datetime import datetime

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI()


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
