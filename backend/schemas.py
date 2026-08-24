from datetime import date, datetime

from pydantic import BaseModel, EmailStr


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserSignup(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class FoodBase(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float = 0
    carbs_per_100g: float = 0
    fat_per_100g: float = 0


class FoodCreate(FoodBase):
    pass


class FoodOut(FoodBase):
    id: int

    class Config:
        from_attributes = True


class LogEntryCreate(BaseModel):
    food_id: int
    grams: float


class QuickLogCreate(BaseModel):
    name: str
    calories: float


class USDAFoodResult(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float


class LogFromSearchCreate(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float = 0
    carbs_per_100g: float = 0
    fat_per_100g: float = 0
    grams: float


class LogEntryOut(BaseModel):
    id: int
    food_id: int
    grams: float
    logged_at: datetime
    food: FoodOut

    class Config:
        from_attributes = True


class WeightEntryCreate(BaseModel):
    weight_kg: float


class WeightEntryOut(BaseModel):
    id: int
    weight_kg: float
    recorded_at: date

    class Config:
        from_attributes = True
