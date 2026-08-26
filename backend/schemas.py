from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserSignup(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    # bcrypt silently ignores/truncates bytes past 72, so cap here rather
    # than let two different-looking passwords hash identically.
    password: str = Field(min_length=8, max_length=72)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfileOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: EmailStr
    daily_calorie_goal: int

    class Config:
        from_attributes = True


class DailyGoalUpdate(BaseModel):
    daily_calorie_goal: int = Field(gt=0, le=20000)


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
    fdc_id: int | None = None

    class Config:
        from_attributes = True


class LogEntryCreate(BaseModel):
    food_id: int
    grams: float = Field(gt=0, le=10000)


class QuickLogCreate(BaseModel):
    name: str
    calories: float


class USDAFoodResult(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float
    carbs_per_100g: float
    fat_per_100g: float
    fdc_id: int | None = None


class LogFromSearchCreate(BaseModel):
    name: str
    calories_per_100g: float
    protein_per_100g: float = 0
    carbs_per_100g: float = 0
    fat_per_100g: float = 0
    fdc_id: int | None = None
    grams: float = Field(gt=0, le=10000)


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


class DashboardFoodItem(BaseModel):
    id: int
    name: str
    weight_grams: float
    calories_per_100g: float
    calculated_calories: float
    logged_at: datetime

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    daily_calorie_goal: int
    calories_consumed: float
    remaining_calories: float
    over_target: bool
    foods: list[DashboardFoodItem]
