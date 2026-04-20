import os
from dotenv import load_dotenv

load_dotenv()

# Bot konfiguratsiyasi
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Admin ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Kanal username (env orqali override mumkin)
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME", "@ideaLsmm_uzb")

# Ma'lumotlar bazasi (SQLite)
DATABASE_NAME = "smm_bot.db"

# SMM Panel API sozlamalari - Peakerr (Asosiy)
SMM_API_URL = os.getenv("SMM_API_URL", "https://peakerr.com/api/v2")
SMM_API_KEY = os.getenv("SMM_API_KEY", "")

# SMMMain API (Ikkinchi panel - O'zbekiston/Rossiya targetli xizmatlar)
SMMMAIN_API_URL = os.getenv("SMMMAIN_API_URL", "https://smmmain.com/api/v2")
SMMMAIN_API_KEY = os.getenv("SMMMAIN_API_KEY", "")

# SMS-Activate API (Virtual telefon raqamlar) - VAK-SMS
SMS_API_KEY = os.getenv("SMS_API_KEY", "")

# 5SIM.NET API (Virtual telefon raqamlar - arzon)
FIVESIM_API_KEY = os.getenv("FIVESIM_API_KEY", "")

# SMSPVA.COM API (Virtual telefon raqamlar - eng arzon!)
SMSPVA_API_KEY = os.getenv("SMSPVA_API_KEY", "")

# To'lov karta raqamlari — barcha qiymatlar .env'dan olinadi (hardcode default YO'Q).
# Agar bironta karta uchun env to'liq to'ldirilmagan bo'lsa — u karta ko'rsatilmaydi.
def _card(env_card: str, env_name: str):
    card = os.getenv(env_card, "").strip()
    name = os.getenv(env_name, "").strip()
    return {"card": card, "name": name} if (card and name) else None


PAYMENT_CARDS = {}
for _label, _ec, _en in (
    ("Click", "CLICK_CARD", "CLICK_NAME"),
    ("Payme", "PAYME_CARD", "PAYME_NAME"),
    ("Uzum", "UZUM_CARD", "UZUM_NAME"),
    ("Visa/MasterCard", "VISA_CARD", "VISA_NAME"),
):
    _data = _card(_ec, _en)
    if _data:
        PAYMENT_CARDS[_label] = _data
