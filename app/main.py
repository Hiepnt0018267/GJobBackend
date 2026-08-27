from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router

app = FastAPI(
    title="GJob Backend API",
    version="0.3.0",
    description="GJob — AI-powered job matching and recruitment platform",
)

# ──────────────────────────────────────────────
# CORS — allow frontend at localhost:3000 (Next.js default)
# ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────────────────────────
# Routers
# ──────────────────────────────────────────────
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")


# ──────────────────────────────────────────────
# Health check endpoints
# ──────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"message": "GJob Backend is running", "version": "0.3.0"}


@app.get("/health/db", tags=["Health"])
def database_health():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {
            "database": "connected",
            "result": result.scalar(),
        }