#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SMM Bot + Mini App API - Combined Runner
Bot va API ni bitta process'da ishga tushiradi
"""
import asyncio
import logging
import os
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_api():
    """FastAPI serverni alohida thread'da ishga tushirish"""
    import uvicorn
    
    port = int(os.getenv("PORT", "8000"))
    
    config = uvicorn.Config(
        "api.main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )
    server = uvicorn.Server(config)
    server.run()


async def run_bot():
    """Telegram bot'ni ishga tushirish"""
    # Bot modulini import qilish
    # main.py import qilinganda router avtomatik dp ga ulanadi
    from main import bot, dp
    
    logger.info("🤖 Bot ishga tushmoqda...")
    
    # Polling boshlash
    await dp.start_polling(bot)


def main():
    """Asosiy funksiya - bot va API ni birga ishga tushirish"""
    logger.info("🚀 SMM Bot + API ishga tushmoqda...")
    
    # Railway uchun: $PORT orqali API ishga tushadi
    # Bot alohida thread'da polling qiladi
    
    port = os.getenv("PORT")
    
    if port:
        # Railway - API asosiy, Bot background
        logger.info(f"✅ Railway mode - API port {port}")
        
        # Bot'ni alohida thread'da ishga tushirish
        def run_bot_thread():
            asyncio.run(run_bot())
        
        bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
        bot_thread.start()
        logger.info("✅ Bot thread ishga tushdi")
        
        # API ni asosiy thread'da ishga tushirish (Railway healthcheck uchun)
        run_api()
    else:
        # Local development - ikkalasi ham ishlaydi
        logger.info("✅ Local mode")
        
        # API ni alohida thread'da
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        logger.info("✅ API server ishga tushdi (port 8000)")
        
        # Bot ni asosiy thread'da
        asyncio.run(run_bot())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Dastur to'xtatildi")
