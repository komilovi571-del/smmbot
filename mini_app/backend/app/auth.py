# -*- coding: utf-8 -*-
"""
Telegram Mini App autentifikatsiyasi
"""
import hmac
import hashlib
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from urllib.parse import parse_qs, unquote

from jose import JWTError, jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import BOT_TOKEN, SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, INIT_DATA_MAX_AGE_SECONDS
from .database import Database
from .models import TelegramUser

security = HTTPBearer(auto_error=False)


def validate_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """
    Telegram Web App init_data ni tekshirish
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        return None
    
    try:
        # Init data ni parse qilish
        parsed = parse_qs(init_data)
        
        # Hash ni olish
        received_hash = parsed.get('hash', [None])[0]
        if not received_hash:
            return None
        
        # auth_date ni tekshirish — init_data yangi bo'lishi shart (replay hujumiga qarshi).
        # Default: 5 daqiqa. Env orqali INIT_DATA_MAX_AGE_SECONDS bilan sozlanadi.
        auth_date = int(parsed.get('auth_date', [0])[0])
        if auth_date <= 0:
            return None
        age = time.time() - auth_date
        if age < 0 or age > INIT_DATA_MAX_AGE_SECONDS:
            return None
        
        # Data-check-string yaratish
        data_check_items = []
        for key, values in sorted(parsed.items()):
            if key != 'hash':
                data_check_items.append(f"{key}={values[0]}")
        data_check_string = '\n'.join(data_check_items)
        
        # Secret key yaratish
        secret_key = hmac.new(
            b"WebAppData",
            BOT_TOKEN.encode(),
            hashlib.sha256
        ).digest()
        
        # Hash hisoblash
        calculated_hash = hmac.new(
            secret_key,
            data_check_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        # Hashlarni solishtirish
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        
        # User ma'lumotlarini parse qilish
        user_data = parsed.get('user', [None])[0]
        if user_data:
            user = json.loads(unquote(user_data))
            return {
                "user": user,
                "auth_date": auth_date,
                "query_id": parsed.get('query_id', [None])[0]
            }
        
        return None
    
    except Exception as e:
        print(f"Init data validation error: {e}")
        return None


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT token yaratish"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """JWT token dekodlash"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """Joriy foydalanuvchini olish"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Autentifikatsiya talab qilinadi")
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise HTTPException(status_code=401, detail="Token yaroqsiz yoki muddati o'tgan")
    
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Token yaroqsiz")
    
    user = Database.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Foydalanuvchi topilmadi")
    
    if user.get("is_banned"):
        raise HTTPException(status_code=403, detail="Foydalanuvchi bloklangan")
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Optional[Dict[str, Any]]:
    """Joriy foydalanuvchini olish (ixtiyoriy)"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
