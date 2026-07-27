import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # Subscription
    SUBSCRIPTION_PRICE = os.getenv("SUBSCRIPTION_PRICE", "25")
    SUPPORT_ID = os.getenv("SUPPORT_ID", "support")
    CHANNEL_ID = os.getenv("CHANNEL_ID", "@channel")
    CURRENCY = os.getenv("CURRENCY", "USDT")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    
    # Binance
    BINANCE_BASE_URL = "https://api.binance.com"
    
    # OCR
    OCR_CONFIDENCE_THRESHOLD = 0.5
    
    # Indicators
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70
    CANDLE_COUNT = 300

settings = Settings()
