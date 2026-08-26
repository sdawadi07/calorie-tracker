import os
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import Base, engine, get_db, run_startup_migrations

load_dotenv()

Base.metadata.create_all(bind=engine)
run_startup_migrations()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """FastAPI's default 422 body puts `detail` as a list of error objects.
    The frontend just wants one readable string (it renders `detail`
    directly), so collapse the first error into plain text instead of
    forcing every caller to know Pydantic's error shape.
    """
    first = exc.errors()[0]
    field = first["loc"][-1] if first.get("loc") else "input"
    return JSONResponse(status_code=422, content={"detail": f"{field}: {first['msg']}"})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch anything that isn't an HTTPException so the client always gets
    JSON with a `detail` string back — never a bare 500 with an HTML/plain
    traceback body that `res.json()` on the frontend would choke on.
    """
    print(f"[unhandled error] {request.method} {request.url.path}: {exc!r}")
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


def get_local_day_bounds_utc(tz_offset_minutes: int) -> tuple[datetime, datetime]:
    """Return (start, end) as UTC datetimes spanning the user's local "today",
    given a JS-style tz offset (Date.getTimezoneOffset(): UTC minus local, in
    minutes — e.g. +300 for US Eastern, -60 for CET).

    We store all timestamps in UTC, but "today" should mean the calling
    user's local calendar day, not the UTC calendar day — otherwise a
    US-based user's dashboard rolls over to a "new day" in the middle of
    their afternoon/evening rather than at their own midnight.
    """
    local_now = datetime.utcnow() - timedelta(minutes=tz_offset_minutes)
    local_midnight = datetime(local_now.year, local_now.month, local_now.day)
    start_utc = local_midnight + timedelta(minutes=tz_offset_minutes)
    end_utc = start_utc + timedelta(days=1)
    return start_utc, end_utc


@app.post("/auth/signup", response_model=schemas.TokenOut)
def signup(user: schemas.UserSignup, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    db_user = models.User(
        first_name=user.first_name,
        last_name=user.last_name,
        email=user.email,
        hashed_password=auth.hash_password(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"access_token": auth.create_access_token(db_user.id)}


@app.post("/auth/login", response_model=schemas.TokenOut)
def login(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if not db_user or not auth.verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"access_token": auth.create_access_token(db_user.id)}


@app.get("/profile/me", response_model=schemas.UserProfileOut)
def get_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@app.put("/profile/goal", response_model=schemas.UserProfileOut)
def update_daily_goal(
    goal: schemas.DailyGoalUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    current_user.daily_calorie_goal = goal.daily_calorie_goal
    db.commit()
    db.refresh(current_user)
    return current_user


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

# USDA foods can list "Energy" more than once (kcal and kJ readings on the
# same food). Only the kcal-labeled entry is a per-100g calorie value we can
# trust; a kJ entry with the same name would silently give a ~4x-too-high
# result if we didn't distinguish them by unit.
KCAL_UNITS = {"KCAL", "kcal"}


def extract_nutrients_per_100g(food_nutrients: list[dict]) -> dict | None:
    """Pull calories/protein/carbs/fat per 100g out of a USDA foodNutrients
    list, keyed by nutrient name rather than array position (USDA does not
    guarantee ordering). Returns None if no usable kcal reading is found —
    callers should skip the food rather than guess.
    """
    values = {"calories_per_100g": None, "protein_per_100g": 0, "carbs_per_100g": 0, "fat_per_100g": 0}
    for nutrient in food_nutrients:
        name = nutrient.get("nutrientName")
        field = NUTRIENT_NAME_MAP.get(name)
        if not field:
            continue
        if field == "calories_per_100g" and nutrient.get("unitName") not in KCAL_UNITS:
            continue
        values[field] = nutrient.get("value", 0)
    if values["calories_per_100g"] is None:
        return None
    return values


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
        values = extract_nutrients_per_100g(item.get("foodNutrients", []))
        if values is None:
            # No trustworthy kcal reading for this food — skip it rather
            # than showing/saving an incorrect calorie value.
            continue
        results.append({"name": item["description"], "fdc_id": item.get("fdcId"), **values})
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
def create_log_entry(
    entry: schemas.LogEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    food = db.query(models.Food).filter(models.Food.id == entry.food_id).first()
    if not food:
        raise HTTPException(status_code=404, detail="Food not found")
    db_entry = models.LogEntry(
        food_id=entry.food_id,
        grams=entry.grams,
        calculated_calories=food.calories_per_100g * entry.grams / 100,
        user_id=current_user.id,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.post("/log/quick", response_model=schemas.LogEntryOut)
def create_quick_log_entry(
    entry: schemas.QuickLogCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """Log food by name + total calories, without tracking per-100g/grams separately."""
    db_food = models.Food(name=entry.name, calories_per_100g=entry.calories)
    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    db_entry = models.LogEntry(
        food_id=db_food.id, grams=100, calculated_calories=entry.calories, user_id=current_user.id
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.post("/log/from_search", response_model=schemas.LogEntryOut)
def create_log_entry_from_search(
    entry: schemas.LogFromSearchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_food = models.Food(
        name=entry.name,
        calories_per_100g=entry.calories_per_100g,
        protein_per_100g=entry.protein_per_100g,
        carbs_per_100g=entry.carbs_per_100g,
        fat_per_100g=entry.fat_per_100g,
        fdc_id=entry.fdc_id,
    )
    db.add(db_food)
    db.commit()
    db.refresh(db_food)

    db_entry = models.LogEntry(
        food_id=db_food.id,
        grams=entry.grams,
        calculated_calories=entry.calories_per_100g * entry.grams / 100,
        user_id=current_user.id,
    )
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.delete("/log/{entry_id}", status_code=204)
def delete_log_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_entry = (
        db.query(models.LogEntry)
        .filter(models.LogEntry.id == entry_id, models.LogEntry.user_id == current_user.id)
        .first()
    )
    if not db_entry:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(db_entry)
    db.commit()


@app.get("/log/today", response_model=list[schemas.LogEntryOut])
def get_today_log(
    tz_offset_minutes: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    start_utc, end_utc = get_local_day_bounds_utc(tz_offset_minutes)
    return (
        db.query(models.LogEntry)
        .filter(
            models.LogEntry.user_id == current_user.id,
            models.LogEntry.logged_at >= start_utc,
            models.LogEntry.logged_at < end_utc,
        )
        .all()
    )


@app.get("/log/today/total")
def get_today_total(
    tz_offset_minutes: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    start_utc, end_utc = get_local_day_bounds_utc(tz_offset_minutes)
    entries = (
        db.query(models.LogEntry)
        .filter(
            models.LogEntry.user_id == current_user.id,
            models.LogEntry.logged_at >= start_utc,
            models.LogEntry.logged_at < end_utc,
        )
        .all()
    )
    # Use the calorie snapshot taken at log time, same as /dashboard/today,
    # rather than recomputing from the (possibly since-edited) Food row.
    total = sum(e.calculated_calories or 0 for e in entries)
    return {"date": str(start_utc.date()), "total_calories": round(total, 1)}


@app.get("/dashboard/today", response_model=schemas.DashboardSummary)
def get_dashboard_today(
    tz_offset_minutes: int = 0,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # "Today" means the caller's local calendar day, not the UTC calendar
    # day — see get_local_day_bounds_utc for why.
    start_utc, end_utc = get_local_day_bounds_utc(tz_offset_minutes)
    entries = (
        db.query(models.LogEntry)
        .filter(
            models.LogEntry.user_id == current_user.id,
            models.LogEntry.logged_at >= start_utc,
            models.LogEntry.logged_at < end_utc,
        )
        .order_by(models.LogEntry.logged_at.asc())
        .all()
    )

    consumed = sum(e.calculated_calories for e in entries)
    goal = current_user.daily_calorie_goal
    remaining = goal - consumed

    return {
        "daily_calorie_goal": goal,
        "calories_consumed": round(consumed, 1),
        "remaining_calories": round(remaining, 1),
        "over_target": consumed > goal,
        "foods": [
            {
                "id": e.id,
                "name": e.food.name,
                "weight_grams": e.grams,
                "calories_per_100g": e.food.calories_per_100g,
                "calculated_calories": round(e.calculated_calories, 1),
                "logged_at": e.logged_at,
            }
            for e in entries
        ],
    }


@app.post("/weight/", response_model=schemas.WeightEntryOut)
def log_weight(
    entry: schemas.WeightEntryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_entry = models.WeightEntry(weight_kg=entry.weight_kg, user_id=current_user.id)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    return db_entry


@app.get("/weight/", response_model=list[schemas.WeightEntryOut])
def list_weight(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.WeightEntry)
        .filter(models.WeightEntry.user_id == current_user.id)
        .order_by(models.WeightEntry.recorded_at.desc())
        .all()
    )


# --- Serve the web frontend -------------------------------------------------
# Mounted last so it never shadows the API routes above (Starlette matches
# routes in registration order). This lets one process/port serve both the
# API and the web UI — no separate frontend server, no CORS setup needed for
# local-network or mobile-browser access: whatever host:port loads the page
# is the same host:port the page's fetch() calls hit.
_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend_web")
if os.path.isdir(_WEB_DIR):
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")
