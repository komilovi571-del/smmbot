# -*- coding: utf-8 -*-
"""
Autentifikatsiya endpointlari
"""
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Body, Request
from typing import Dict, Any
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..auth import validate_init_data, create_access_token
from ..database import Database
from ..models import AuthResponse
from ..config import ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class AuthRequest(BaseModel):
    init_data: str


@router.post("")
@limiter.limit("10/minute")
async def authenticate_telegram_simple(request: Request, body: AuthRequest):
    """
    Telegram Mini App autentifikatsiyasi - /api/auth endpoint
    Frontend buni ishlatadi
    """
    # Init data ni tekshirish
    validated = validate_init_data(body.init_data)
    
    if not validated:
        raise HTTPException(status_code=401, detail="Init data yaroqsiz")
    
    user_data = validated.get("user")
    if not user_data:
        raise HTTPException(status_code=401, detail="Foydalanuvchi ma'lumotlari topilmadi")
    
    user_id = user_data.get("id")
    username = user_data.get("username", "")
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    
    # Foydalanuvchini bazada tekshirish/yaratish
    existing_user = Database.get_user(user_id)
    
    if not existing_user:
        # Yangi foydalanuvchi
        Database.add_user(user_id, username, full_name)
        existing_user = Database.get_user(user_id)
    
    if existing_user and existing_user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Hisobingiz bloklangan")
    
    return {
        "success": True,
        "user": {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "balance": existing_user.get("balance", 0) if existing_user else 0,
            "referral_count": existing_user.get("referral_count", 0) if existing_user else 0,
            "referral_earnings": existing_user.get("referral_earnings", 0) if existing_user else 0,
            "is_banned": bool(existing_user.get("is_banned", 0)) if existing_user else False,
            "created_at": existing_user.get("created_at") if existing_user else None
        }
    }


@router.post("/telegram", response_model=AuthResponse)
async def authenticate_telegram(init_data: str = Body(..., embed=True)):
    """
    Telegram Mini App autentifikatsiyasi
    """
    # Init data ni tekshirish
    validated = validate_init_data(init_data)
    
    if not validated:
        raise HTTPException(status_code=401, detail="Init data yaroqsiz")
    
    user_data = validated.get("user")
    if not user_data:
        raise HTTPException(status_code=401, detail="Foydalanuvchi ma'lumotlari topilmadi")
    
    user_id = user_data.get("id")
    username = user_data.get("username", "")
    first_name = user_data.get("first_name", "")
    last_name = user_data.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    
    # Foydalanuvchini bazada tekshirish/yaratish
    existing_user = Database.get_user(user_id)
    
    if not existing_user:
        # Yangi foydalanuvchi
        Database.add_user(user_id, username, full_name)
        existing_user = Database.get_user(user_id)
    
    if existing_user and existing_user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Hisobingiz bloklangan")
    
    # Token yaratish
    access_token = create_access_token(
        data={"user_id": user_id, "username": username},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    
    return AuthResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "balance": existing_user.get("balance", 0) if existing_user else 0,
            "is_premium": user_data.get("is_premium", False)
        }
    )


@router.post("/verify")
async def verify_token(token: str = Body(..., embed=True)) -> Dict[str, Any]:
    """
    Token tekshirish
    """
    from ..auth import decode_token
    
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token yaroqsiz")
    
    user_id = payload.get("user_id")
    user = Database.get_user(user_id)
    
    if not user:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi")
    
    return {
        "valid": True,
        "user_id": user_id,
        "username": payload.get("username"),
        "balance": user.get("balance", 0)
    }
