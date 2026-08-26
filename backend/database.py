import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Render (and most hosts) inject DATABASE_URL as an env var; falls back to
# local Postgres for development. Some hosts still hand out "postgres://"
# URLs, which SQLAlchemy 2.x no longer accepts, so normalize it.
SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/calorie_tracker")
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_startup_migrations():
    """Additively patch columns added after the tables already existed in
    someone's database. There's no migration framework in this project (the
    schema is otherwise managed via Base.metadata.create_all), so this keeps
    existing rows intact instead of requiring a drop/recreate.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_calorie_goal "
            "INTEGER NOT NULL DEFAULT 2000"
        ))
        conn.execute(text("ALTER TABLE foods ADD COLUMN IF NOT EXISTS fdc_id INTEGER"))
        conn.execute(text(
            "ALTER TABLE log_entries ADD COLUMN IF NOT EXISTS calculated_calories "
            "DOUBLE PRECISION"
        ))
        conn.execute(text(
            "UPDATE log_entries SET calculated_calories = foods.calories_per_100g * "
            "log_entries.grams / 100 FROM foods WHERE foods.id = log_entries.food_id "
            "AND log_entries.calculated_calories IS NULL"
        ))
        _normalize_existing_emails(conn)


def _normalize_existing_emails(conn):
    """Lowercase any accounts created before email normalization was added,
    so old mixed-case signups can still log in. Skips (and reports) any pair
    that would collide once lowercased, since merging accounts needs a human
    decision, not a silent migration.
    """
    rows = conn.execute(text("SELECT id, email FROM users WHERE email <> lower(email)")).fetchall()
    for row in rows:
        conflict = conn.execute(
            text("SELECT 1 FROM users WHERE lower(email) = :email AND id <> :id"),
            {"email": row.email.lower(), "id": row.id},
        ).first()
        if conflict:
            print(f"[startup migration] Skipping email normalization for user {row.id} "
                  f"({row.email}) — a lowercase match already exists. Resolve manually.")
            continue
        conn.execute(
            text("UPDATE users SET email = lower(email) WHERE id = :id"),
            {"id": row.id},
        )
