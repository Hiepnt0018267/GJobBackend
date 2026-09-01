from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.database import engine
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.jobs import router as jobs_router
from app.routers.recruiters import router as recruiters_router
from app.routers.cvs import router as cvs_router
from app.routers.cv_templates import router as cv_templates_router
from app.routers.applications import router as applications_router
from app.routers.admin import router as admin_router

app = FastAPI(
    title="GJob Backend API",
    version="0.3.0",
    description="GJob â€” AI-powered job matching and recruitment platform",
)


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


app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(jobs_router, prefix="/api/v1")
app.include_router(recruiters_router, prefix="/api/v1")
app.include_router(cvs_router, prefix="/api/v1")
app.include_router(cv_templates_router, prefix="/api/v1")
app.include_router(applications_router, prefix="/api/v1")
app.include_router(admin_router, prefix="/api/v1")



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
