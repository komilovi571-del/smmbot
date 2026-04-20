# -*- coding: utf-8 -*-
"""
Mini App Backend konfiguratsiyasi
"""
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv

# .env faylni yuklash (parent directory'dan)
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)

# Bot konfiguratsiyasi
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:8000")  # Bot API URL (Railway yoki local)

# Admin ID'lar ro'yxati (bir nechta admin qo'shish uchun)
ADMIN_IDS = [ADMIN_ID]  # Qo'shimcha adminlar qo'shish uchun ro'yxatga qo'shing

# Ma'lumotlar bazasi
DATABASE_PATH = Path(__file__).parent.parent.parent.parent / "smm_bot.db"
DATABASE_NAME = str(DATABASE_PATH)

# SMM Panel API sozlamalari
SMM_API_URL = os.getenv("SMM_API_URL", "https://peakerr.com/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY", "")
SMMMAIN_API_URL = os.getenv("SMMMAIN_API_URL", "https://smmmain.com/api/v2")
SMMMAIN_API_KEY = os.getenv("SMMMAIN_API_KEY", "")

# SMS API
SMS_API_KEY = os.getenv("SMS_API_KEY", "")
FIVESIM_API_KEY = os.getenv("FIVESIM_API_KEY", "")
SMSPVA_API_KEY = os.getenv("SMSPVA_API_KEY", "")

# Click to'lov tizimi
# Click merchant kabinetdan olish: https://merchant.click.uz
CLICK_MERCHANT_ID = os.getenv("CLICK_MERCHANT_ID", "")
CLICK_SERVICE_ID = os.getenv("CLICK_SERVICE_ID", "")
CLICK_SECRET_KEY = os.getenv("CLICK_SECRET_KEY", "")

# CORS origins — Telegram regex'i main.py ichida qo'shiladi
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://web.telegram.org",
    FRONTEND_URL,
]

# JWT sozlamalari
# MUHIM: Production'da JWT_SECRET_KEY albatta env'ga o'rnatilishi kerak.
# Agar env yo'q bo'lsa — xavfsiz ishlamaymiz, startup'da xato beramiz.
_ENV_SECRET = os.getenv("JWT_SECRET_KEY") or os.getenv("SECRET_KEY")
if not _ENV_SECRET:
    # Dev fallback: BOT_TOKEN'dan kriptografik tarzda hosil qilingan kalit (tokenning o'zi emas)
    if BOT_TOKEN:
        import hashlib
        _ENV_SECRET = hashlib.sha256(("jwt-v1::" + BOT_TOKEN).encode()).hexdigest()
    else:
        raise RuntimeError(
            "JWT_SECRET_KEY env variable o'rnatilmagan. "
            "Iltimos, .env fayliga JWT_SECRET_KEY=<tasodifiy uzoq string> qo'shing."
        )
if len(_ENV_SECRET) < 32:
    raise RuntimeError("JWT_SECRET_KEY juda qisqa (kamida 32 belgi bo'lishi kerak).")
SECRET_KEY = _ENV_SECRET
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 soat default

# Telegram init_data auth_date oynasi (soniyalarda). Default 5 daqiqa.
INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("INIT_DATA_MAX_AGE_SECONDS", "300"))

# To'lov kartalari — barcha qiymatlar .env'dan olinadi, hardcode default yo'q.
def _card(env_card: str, env_name: str) -> Dict[str, str]:
    return {
        "card": os.getenv(env_card, "").strip(),
        "name": os.getenv(env_name, "").strip(),
    }


PAYMENT_CARDS: Dict[str, Dict[str, str]] = {}
for _label, _ec, _en in (
    ("Click", "CLICK_CARD", "CLICK_NAME"),
    ("Payme", "PAYME_CARD", "PAYME_NAME"),
    ("Uzum", "UZUM_CARD", "UZUM_NAME"),
):
    _data = _card(_ec, _en)
    if _data["card"] and _data["name"]:
        PAYMENT_CARDS[_label] = _data
