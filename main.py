import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from bot.handlers import router
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

os.makedirs('/tmp/torch_cache', exist_ok=True)
os.makedirs('/tmp/easyocr_models', exist_ok=True)
os.environ['TORCH_HOME'] = '/tmp/torch_cache'

bot = None

async def main():
    global bot
    try:
        logger.info("🤖 Starting Crypto Signal Bot...")
        
        bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        
        dp = Dispatcher()
        dp.include_router(router)
        
        logger.info("✅ Bot started successfully!")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        if bot:
            await bot.session.close()
        logger.info("🛑 Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        sys.exit(1)
