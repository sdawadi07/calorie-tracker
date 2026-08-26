from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    daily_calorie_goal = Column(Integer, nullable=False, default=2000, server_default="2000")


class Food(Base):
    __tablename__ = "foods"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    calories_per_100g = Column(Float, nullable=False)
    protein_per_100g = Column(Float, default=0)
    carbs_per_100g = Column(Float, default=0)
    fat_per_100g = Column(Float, default=0)
    fdc_id = Column(Integer, nullable=True)

    log_entries = relationship("LogEntry", back_populates="food")


class LogEntry(Base):
    __tablename__ = "log_entries"

    id = Column(Integer, primary_key=True, index=True)
    food_id = Column(Integer, ForeignKey("foods.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    grams = Column(Float, nullable=False)
    # Snapshot of calories at log time, so edits to a shared Food row (or
    # future recalculation logic) never silently rewrite past history.
    calculated_calories = Column(Float, nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow)

    food = relationship("Food", back_populates="log_entries")


class WeightEntry(Base):
    __tablename__ = "weight_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    weight_kg = Column(Float, nullable=False)
    recorded_at = Column(Date, default=datetime.utcnow)