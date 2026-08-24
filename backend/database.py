import os

from sqlalchemy import create_engine
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
