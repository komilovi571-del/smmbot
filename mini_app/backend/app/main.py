# -*- coding: utf-8 -*-
"""
SMM Mini App - FastAPI Backend
Asosiy kirish nuqtasi
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from .config import CORS_ORIGINS
from .routers import auth, user, services, orders, payments, sms
from .routers import click as click_router
from .database import Database

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle"""
    # Startup
    print("🚀 SMM Mini App Backend ishga tushmoqda...")
    # Click to'lovlar jadvalini yaratish
    Database.init_click_payments_table()
    yield
    # Shutdown
    print("👋 SMM Mini App Backend to'xtatilmoqda...")


# FastAPI ilovasi
app = FastAPI(
    title="SMM Mini App API",
    description="Telegram Mini App uchun SMM xizmatlari API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — aniq origin'lar ro'yxati (xavfsizlik uchun "*" ishlatilmaydi)
# Telegram Web App domain'lari va konfiguratsiyadagi FRONTEND_URL ruxsat etilgan.
# Mahalliy rivojlantirish origin'lari (localhost:3000, 5173) config.py ichida.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"https://.*\.telegram\.org",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

# Routerlar
app.include_router(auth.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(services.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(sms.router, prefix="/api")
app.include_router(click_router.router, prefix="/api")

# Admin panel router
from .routers import admin as admin_router
app.include_router(admin_router.router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "SMM Mini App API",
        "version": "1.0.0",
        "status": "active",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with DB ping"""
    try:
        from .database import get_db
        with get_db() as conn:
            conn.execute("SELECT 1")
        return {"status": "healthy", "database": "ok"}
    except Exception as e:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": str(e)}
        )


@app.get("/api/settings")
async def get_public_settings():
    """Umumiy sozlamalarni olish"""
    from .database import Database
    
    return {
        "usd_rate": int(Database.get_setting("usd_rate", "12900")),
        "rub_rate": int(Database.get_setting("rub_rate", "140")),
        "min_deposit": int(Database.get_setting("min_deposit", "5000")),
        "referral_bonus": int(Database.get_setting("referral_bonus", "500"))
    }
