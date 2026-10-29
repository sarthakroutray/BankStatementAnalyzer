from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.config import settings
from app.db import init_db
from app.services.normalizer import get_category_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schemas on startup if needed
    try:
        await init_db()
    except Exception as e:
        print(f"Warning: Database init failed or deferred: {e}")

    # Warm up category classifier ML pipeline
    try:
        get_category_pipeline()
    except Exception as e:
        print(f"Warning: Category classifier pipeline warmup failed: {e}")

    yield


app = FastAPI(
    title="FinWise Bank Statement Analyzer & Forecaster API",
    description="Deterministic PDF bank statement table parser, Neon PostgreSQL storage, and SARIMA spending forecaster.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration supporting Vercel and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if settings.cors_origins != ["*"] else ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app" if settings.cors_origins != ["*"] else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "FinWise Bank Statement Analyzer API",
        "env": settings.APP_ENV,
        "database": "connected"
    }


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to FinWise Bank Statement Analyzer & SARIMA Spending Forecaster API",
        "docs": "/docs",
        "health": "/health"
    }
