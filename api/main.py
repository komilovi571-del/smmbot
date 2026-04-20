# -*- coding: utf-8 -*-
"""
SMM Mini App API - FastAPI Backend
Bot bilan bitta server'da ishlaydi
"""
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import hashlib
import hmac
import json
import os
from urllib.parse import unquote
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Static files papkasi
STATIC_DIR = Path(__file__).parent.parent / "static"

from database import (
    get_user, add_user, update_balance, get_user_orders,
    get_setting, get_user_payments_admin, get_user_by_phone
)
from config import BOT_TOKEN

# Static files papkasi
STATIC_DIR = Path(__file__).parent.parent / "static"
print(f"[DEBUG] __file__ = {__file__}")
print(f"[DEBUG] STATIC_DIR = {STATIC_DIR}")
print(f"[DEBUG] STATIC_DIR.exists() = {STATIC_DIR.exists()}")
if STATIC_DIR.exists():
    print(f"[DEBUG] STATIC_DIR contents: {list(STATIC_DIR.iterdir())}")

# FastAPI app
app = FastAPI(
    title="SMM Mini App API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url=None
)

# CORS - Telegram WebApp va local development uchun
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== MODELS ====================

class TelegramUser(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None

class AuthRequest(BaseModel):
    init_data: str

class AuthResponse(BaseModel):
    success: bool
    user: Optional[dict] = None
    token: Optional[str] = None

class UserResponse(BaseModel):
    user_id: int
    username: Optional[str]
    full_name: str
    balance: int
    referral_count: int
    referral_earnings: int
    is_banned: bool
    created_at: str


# ==================== AUTH ====================

def validate_init_data(init_data: str) -> Optional[dict]:
    """Telegram WebApp init_data ni tekshirish"""
    try:
        # Parse init_data
        parsed = dict(x.split('=') for x in unquote(init_data).split('&'))
        
        # Get hash
        received_hash = parsed.pop('hash', None)
        if not received_hash:
            return None
        
        # Create data check string
        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )
        
        # Create secret key
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Calculate hash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Verify
        if calculated_hash != received_hash:
            return None
        
        # Parse user data
        user_data = json.loads(parsed.get('user', '{}'))
        return user_data
    except Exception as e:
        print(f"Init data validation error: {e}")
        return None


async def get_current_user(x_telegram_init_data: str = Header(None)) -> dict:
    """Joriy foydalanuvchini olish"""
    if not x_telegram_init_data:
        raise HTTPException(status_code=401, detail="Init data required")
    
    user_data = validate_init_data(x_telegram_init_data)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid init data")
    
    return user_data


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Agar static frontend mavjud bo'lsa — index.html, aks holda API status"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"status": "ok", "service": "SMM Mini App API"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/api/settings")
async def get_settings():
    """Umumiy sozlamalar"""
    return {
        "usd_rate": int(get_setting("usd_rate") or 12900),
        "rub_rate": int(get_setting("rub_rate") or 140),
        "min_deposit": int(get_setting("min_deposit") or 5000),
        "referral_bonus": int(get_setting("referral_bonus") or 500),
    }


@app.post("/api/auth")
async def auth(request: AuthRequest):
    """Telegram WebApp autentifikatsiyasi"""
    user_data = validate_init_data(request.init_data)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid init data")
    
    user_id = user_data.get('id')
    username = user_data.get('username', '')
    first_name = user_data.get('first_name', '')
    last_name = user_data.get('last_name', '')
    full_name = f"{first_name} {last_name}".strip()
    
    # User mavjudligini tekshirish
    user = get_user(user_id)
    
    if not user:
        # Yangi user yaratish
        add_user(user_id, username, full_name)
        user = get_user(user_id)
    
    return {
        "success": True,
        "user": {
            "user_id": user[0],
            "username": user[1],
            "full_name": user[2],
            "balance": user[3],
            "referral_count": user[4] if len(user) > 4 else 0,
            "referral_earnings": user[5] if len(user) > 5 else 0,
            "is_banned": bool(user[7]) if len(user) > 7 else False,
            "created_at": user[8] if len(user) > 8 else datetime.now().isoformat()
        }
    }


@app.get("/api/user/me")
async def get_me(user_data: dict = Depends(get_current_user)):
    """Joriy foydalanuvchi ma'lumotlari"""
    user_id = user_data.get('id')
    user = get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "user_id": user[0],
        "username": user[1],
        "full_name": user[2],
        "balance": user[3],
        "referral_count": user[4] if len(user) > 4 else 0,
        "referral_earnings": user[5] if len(user) > 5 else 0,
        "is_banned": bool(user[7]) if len(user) > 7 else False,
        "created_at": user[8] if len(user) > 8 else ""
    }


class CreateUserRequest(BaseModel):
    user_id: int
    username: str = ""
    full_name: str = "Foydalanuvchi"


@app.post("/api/user/create")
async def create_or_get_user(request: CreateUserRequest):
    """Foydalanuvchi yaratish yoki mavjudini qaytarish"""
    user = get_user(request.user_id)
    
    if not user:
        # Yangi user yaratish
        add_user(request.user_id, request.username, request.full_name)
        user = get_user(request.user_id)
    
    if not user:
        raise HTTPException(status_code=500, detail="Failed to create user")
    
    return {
        "success": True,
        "user": {
            "user_id": user[0],
            "username": user[1],
            "full_name": user[2],
            "balance": user[3],
            "referral_count": user[4] if len(user) > 4 else 0,
            "referral_earnings": user[5] if len(user) > 5 else 0,
            "is_banned": bool(user[7]) if len(user) > 7 else False,
            "created_at": user[8] if len(user) > 8 else ""
        }
    }


@app.get("/api/user/by-phone/{phone}")
async def get_user_by_phone_number(phone: str):
    """Telefon raqam bo'yicha foydalanuvchi ma'lumotlarini olish"""
    # Telefon raqamni tozalash (faqat raqamlar)
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    user = get_user_by_phone(clean_phone)
    
    if not user:
        # +998 bilan ham tekshiramiz
        if not clean_phone.startswith('998'):
            clean_phone = '998' + clean_phone
            user = get_user_by_phone(clean_phone)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "success": True,
        "user": {
            "user_id": user[0],
            "username": user[1],
            "full_name": user[2],
            "balance": user[3],
            "referral_count": user[4] if len(user) > 4 else 0,
            "referral_earnings": user[5] if len(user) > 5 else 0,
            "is_banned": bool(user[7]) if len(user) > 7 else False,
            "created_at": user[8] if len(user) > 8 else ""
        }
    }


@app.get("/api/user/{user_id}")
async def get_user_by_id(user_id: int):
    """User ID bo'yicha foydalanuvchi ma'lumotlarini olish"""
    user = get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "success": True,
        "user": {
            "user_id": user[0],
            "username": user[1],
            "full_name": user[2],
            "balance": user[3],
            "referral_count": user[4] if len(user) > 4 else 0,
            "referral_earnings": user[5] if len(user) > 5 else 0,
            "is_banned": bool(user[7]) if len(user) > 7 else False,
            "created_at": user[8] if len(user) > 8 else ""
        }
    }


@app.get("/api/user/balance")
async def get_balance(user_data: dict = Depends(get_current_user)):
    """Foydalanuvchi balansini olish"""
    user_id = user_data.get('id')
    user = get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"balance": user[3]}


@app.get("/api/orders")
async def get_orders(user_data: dict = Depends(get_current_user)):
    """Foydalanuvchi buyurtmalari"""
    user_id = user_data.get('id')
    orders = get_user_orders(user_id)
    
    return {
        "orders": [
            {
                "id": o[0],
                "user_id": o[1],
                "service_type": o[2],
                "service_name": o[3],
                "quantity": o[4],
                "price": o[5],
                "status": o[6],
                "link": o[7],
                "panel_order_id": o[8] if len(o) > 8 else None,
                "created_at": o[9] if len(o) > 9 else ""
            }
            for o in orders
        ]
    }


@app.get("/api/payments")
async def get_payments(user_data: dict = Depends(get_current_user)):
    """To'lovlar tarixi"""
    user_id = user_data.get('id')
    payments = get_user_payments_admin(user_id)
    
    return {
        "payments": [
            {
                "id": p[0],
                "user_id": p[1],
                "amount": p[2],
                "method": p[3],
                "status": p[4],
                "created_at": p[5] if len(p) > 5 else ""
            }
            for p in payments
        ]
    }


@app.get("/api/referral/stats")
async def get_referral_stats(user_data: dict = Depends(get_current_user)):
    """Referal statistikasi"""
    user_id = user_data.get('id')
    user = get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "referral_count": user[4] if len(user) > 4 else 0,
        "referral_earnings": user[5] if len(user) > 5 else 0,
        "referral_link": f"https://t.me/SmmXizmatlari_bot?start=ref{user_id}",
        "referrals": []
    }


# ==================== PLATFORMS & SERVICES ====================

@app.get("/api/platforms")
async def get_platforms():
    """Mavjud platformalar"""
    return {
        "platforms": [
            {"id": "telegram", "name": "Telegram", "emoji": "📱", "color": "#0088cc"},
            {"id": "instagram", "name": "Instagram", "emoji": "📸", "color": "#E1306C"},
            {"id": "youtube", "name": "YouTube", "emoji": "📺", "color": "#FF0000"},
            {"id": "tiktok", "name": "TikTok", "emoji": "🎵", "color": "#000000"},
        ]
    }


@app.get("/api/platforms/{platform_id}/categories")
async def get_categories(platform_id: str):
    """Platforma kategoriyalari"""
    categories = {
        "telegram": [
            {"id": "members", "name": "A'zolar", "emoji": "👥"},
            {"id": "views", "name": "Ko'rishlar", "emoji": "👁"},
            {"id": "reactions", "name": "Reaksiyalar", "emoji": "❤️"},
        ],
        "instagram": [
            {"id": "followers", "name": "Obunachilar", "emoji": "👥"},
            {"id": "likes", "name": "Layklar", "emoji": "❤️"},
            {"id": "views", "name": "Ko'rishlar", "emoji": "👁"},
            {"id": "comments", "name": "Izohlar", "emoji": "💬"},
        ],
        "youtube": [
            {"id": "subscribers", "name": "Obunachilar", "emoji": "👥"},
            {"id": "views", "name": "Ko'rishlar", "emoji": "👁"},
            {"id": "likes", "name": "Layklar", "emoji": "👍"},
        ],
        "tiktok": [
            {"id": "followers", "name": "Obunachilar", "emoji": "👥"},
            {"id": "likes", "name": "Layklar", "emoji": "❤️"},
            {"id": "views", "name": "Ko'rishlar", "emoji": "👁"},
        ],
    }
    
    return {"categories": categories.get(platform_id, [])}


@app.get("/api/services/{platform_id}/{category_id}")
async def get_services(platform_id: str, category_id: str):
    """Xizmatlar ro'yxati"""
    # Bu yerda database'dan real xizmatlar olinadi
    # Hozircha mock data
    services = {
        "telegram-members": [
            {"id": "1", "name": "Telegram a'zolar - Real", "description": "Haqiqiy foydalanuvchilar", "price_per_1000": 15000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
            {"id": "2", "name": "Telegram a'zolar - Premium", "description": "Premium sifat", "price_per_1000": 25000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "60 kun", "speed": "5K/kun"},
        ],
        "telegram-views": [
            {"id": "3", "name": "Telegram ko'rishlar - Tez", "description": "Tezkor yetkazish", "price_per_1000": 5000, "min_quantity": 100, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "100K/kun"},
        ],
        "telegram-reactions": [
            {"id": "5", "name": "Telegram reaksiyalar", "description": "Turli reaksiyalar", "price_per_1000": 10000, "min_quantity": 50, "max_quantity": 100000, "guarantee": "Yo'q", "speed": "20K/kun"},
        ],
        "instagram-followers": [
            {"id": "6", "name": "Instagram obunachilar", "description": "Aralash obunachilar", "price_per_1000": 20000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
        ],
        "instagram-likes": [
            {"id": "8", "name": "Instagram layklar", "description": "Tezkor layklar", "price_per_1000": 8000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "Yo'q", "speed": "50K/kun"},
        ],
        "instagram-views": [
            {"id": "9", "name": "Instagram ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 3000, "min_quantity": 100, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "100K/kun"},
        ],
        "instagram-comments": [
            {"id": "10", "name": "Instagram izohlar", "description": "Custom izohlar", "price_per_1000": 50000, "min_quantity": 10, "max_quantity": 10000, "guarantee": "Yo'q", "speed": "1K/kun"},
        ],
        "youtube-subscribers": [
            {"id": "11", "name": "YouTube obunachilar", "description": "Kanal obunachilar", "price_per_1000": 50000, "min_quantity": 100, "max_quantity": 10000, "guarantee": "30 kun", "speed": "1K/kun"},
        ],
        "youtube-views": [
            {"id": "12", "name": "YouTube ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 15000, "min_quantity": 1000, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "50K/kun"},
        ],
        "youtube-likes": [
            {"id": "13", "name": "YouTube layklar", "description": "Video layklar", "price_per_1000": 20000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "30 kun", "speed": "5K/kun"},
        ],
        "tiktok-followers": [
            {"id": "14", "name": "TikTok obunachilar", "description": "Profil obunachilar", "price_per_1000": 18000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
        ],
        "tiktok-likes": [
            {"id": "15", "name": "TikTok layklar", "description": "Video layklar", "price_per_1000": 6000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "Yo'q", "speed": "50K/kun"},
        ],
        "tiktok-views": [
            {"id": "16", "name": "TikTok ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 2000, "min_quantity": 1000, "max_quantity": 10000000, "guarantee": "Yo'q", "speed": "1M/kun"},
        ],
    }
    
    key = f"{platform_id}-{category_id}"
    return {"services": services.get(key, [])}


@app.get("/api/service/{service_id}")
async def get_service(service_id: str):
    """Bitta xizmat haqida"""
    # Mock - real bo'lsa database'dan olinadi
    all_services = {
        "1": {"id": "1", "name": "Telegram a'zolar - Real", "description": "Haqiqiy foydalanuvchilar", "price_per_1000": 15000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
        "2": {"id": "2", "name": "Telegram a'zolar - Premium", "description": "Premium sifat", "price_per_1000": 25000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "60 kun", "speed": "5K/kun"},
        "3": {"id": "3", "name": "Telegram ko'rishlar - Tez", "description": "Tezkor yetkazish", "price_per_1000": 5000, "min_quantity": 100, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "100K/kun"},
        "5": {"id": "5", "name": "Telegram reaksiyalar", "description": "Turli reaksiyalar", "price_per_1000": 10000, "min_quantity": 50, "max_quantity": 100000, "guarantee": "Yo'q", "speed": "20K/kun"},
        "6": {"id": "6", "name": "Instagram obunachilar", "description": "Aralash obunachilar", "price_per_1000": 20000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
        "8": {"id": "8", "name": "Instagram layklar", "description": "Tezkor layklar", "price_per_1000": 8000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "Yo'q", "speed": "50K/kun"},
        "9": {"id": "9", "name": "Instagram ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 3000, "min_quantity": 100, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "100K/kun"},
        "10": {"id": "10", "name": "Instagram izohlar", "description": "Custom izohlar", "price_per_1000": 50000, "min_quantity": 10, "max_quantity": 10000, "guarantee": "Yo'q", "speed": "1K/kun"},
        "11": {"id": "11", "name": "YouTube obunachilar", "description": "Kanal obunachilar", "price_per_1000": 50000, "min_quantity": 100, "max_quantity": 10000, "guarantee": "30 kun", "speed": "1K/kun"},
        "12": {"id": "12", "name": "YouTube ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 15000, "min_quantity": 1000, "max_quantity": 1000000, "guarantee": "Yo'q", "speed": "50K/kun"},
        "13": {"id": "13", "name": "YouTube layklar", "description": "Video layklar", "price_per_1000": 20000, "min_quantity": 50, "max_quantity": 50000, "guarantee": "30 kun", "speed": "5K/kun"},
        "14": {"id": "14", "name": "TikTok obunachilar", "description": "Profil obunachilar", "price_per_1000": 18000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "30 kun", "speed": "10K/kun"},
        "15": {"id": "15", "name": "TikTok layklar", "description": "Video layklar", "price_per_1000": 6000, "min_quantity": 100, "max_quantity": 100000, "guarantee": "Yo'q", "speed": "50K/kun"},
        "16": {"id": "16", "name": "TikTok ko'rishlar", "description": "Video ko'rishlar", "price_per_1000": 2000, "min_quantity": 1000, "max_quantity": 10000000, "guarantee": "Yo'q", "speed": "1M/kun"},
    }
    
    service = all_services.get(service_id)
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return service


# ==================== STATIC FILES (Mini App Frontend) ====================

# Static assets (JS, CSS, images) - /assets/ papkasini mount qilish
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="static_assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all - barcha yo'nalishlar uchun index.html qaytarish"""
        # API route'larini o'tkazib yuborish
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Fayl mavjudligini tekshirish (masalan, favicon.ico, robots.txt)
        file_path = STATIC_DIR / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        # Boshqa barcha yo'nalishlar uchun index.html (SPA routing)
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        
        raise HTTPException(status_code=404, detail="Not found")
