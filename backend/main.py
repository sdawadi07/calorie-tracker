from fastapi import FastAPI

app = FastAPI()

@app.get("/foods/{food_name}")
def get_food(food_name: str):
    return {
        "food": food_name,
        "calories_per_100g": 100,
        "note": "Fake data for now - we'll connect to USDA later"
    } 
