# Calorie Tracker

A personal calorie and weight tracking app. Log food (searched from real
USDA nutrition data or entered manually), see your daily calorie total,
and track your weight over time.

Built as a learning project: FastAPI + PostgreSQL backend, React
Native (Expo) frontend.

## Features

- **Accounts** — sign up / log in, your data is private to your account
- **Food search** — search real foods via USDA FoodData Central, pick a
  result, enter grams eaten, and it logs the calories automatically
- **Manual entry** — fallback for foods not found in search
- **Daily log** — running calorie total for today, long-press an entry
  to delete it
- **Weight tracking** — log weight over time, see history

## Tech stack

| Layer | Tech |
|---|---|
| Backend | Python, FastAPI |
| Database | PostgreSQL (via SQLAlchemy) |
| Auth | JWT tokens, bcrypt-hashed passwords |
| Frontend | React Native (Expo), TypeScript |
| Food data | [USDA FoodData Central](https://fdc.nal.usda.gov/) |

## Project structure

```
backend/
  main.py          API routes (auth, food search, log, weight)
  models.py        Database tables
  schemas.py       Request/response validation
  auth.py          Password hashing + JWT logic
  database.py      Database connection
  requirements.txt Python dependencies

frontend/
  App.tsx          Entire app UI (login/signup, food log, weight)
```

## Setup

### Backend

1. Create a PostgreSQL database named `calorie_tracker`.
2. Install dependencies:
   ```
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in real values:
   ```
   cp .env.example .env
   ```
   - `USDA_API_KEY` — free key from [api.data.gov/signup](https://api.data.gov/signup/)
   - `JWT_SECRET` — any random string, e.g. `python3 -c "import secrets; print(secrets.token_hex(32))"`
4. Run the server:
   ```
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```
   Tables are created automatically on first run.

### Frontend

1. Install dependencies:
   ```
   cd frontend
   npm install
   ```
2. In `App.tsx`, set `API_BASE_URL` to your machine's LAN IP (so a phone
   on the same WiFi can reach the backend), e.g. `http://192.168.1.23:8000`.
3. Run it:
   ```
   npx expo start
   ```
   - Press `w` for web, or scan the QR code with the **Expo Go** app on
     your phone (same WiFi network required).
   - Expo Go on the App Store currently supports SDK 54 — this project
     is pinned to that version to match.

## Status

Actively being built. Core flow (accounts, food search + logging,
weight tracking) is working end-to-end.
