import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime, timedelta

from ocr.ocr_engine import OCREngine
from services.binance_service import BinanceService
from analysis.indicator_calculator import IndicatorCalculator
from analysis.signal_generator import SignalGenerator
from analysis.backtest_engine import BacktestEngine
from config.settings import settings

logger = logging.getLogger(__name__)
router = Router()

ocr_engine = OCREngine()
binance_service = BinanceService()
signal_generator = SignalGenerator()

# === توابع کمکی ===
async def check_membership(user_id: int) -> bool:
    try:
        from main import bot
        member = await bot.get_chat_member(settings.CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بررسی عضویت", callback_data="check_membership")]
    ])

def backtest_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 ۳ ماهه", callback_data="backtest_3m"),
            InlineKeyboardButton(text="📊 ۶ ماهه", callback_data="backtest_6m")
        ],
        [
            InlineKeyboardButton(text="📊 ۱ ساله", callback_data="backtest_1y"),
            InlineKeyboardButton(text="📊 ۲ ساله", callback_data="backtest_2y")
        ],
        [InlineKeyboardButton(text="🔙 بازگشت", callback_data="back_to_menu")]
    ])

# === دستورات ===
@router.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    is_member = await check_membership(user_id)
    
    if is_member:
        await message.answer(
            "✅ اشتراک شما فعال است!\n\n"
            "📸 عکس چارت را بفرستید تا تحلیل دریافت کنید.\n\n"
            "⚡ دستورات ویژه:\n"
            "/backtest - اجرای بک‌تست"
        )
    else:
        await message.answer(
            f"═══════════════════════════════════════\n"
            f"🤖 ربات تحلیلگر نهادی ارز دیجیتال\n"
            f"═══════════════════════════════════════\n\n"
            f"سلام! 👋\n\n"
            f"برای استفاده از این ربات، ابتدا باید اشتراک تهیه کنید.\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"💎 قیمت اشتراک مادام‌العمر:\n\n"
            f"💰 {settings.SUBSCRIPTION_PRICE} تتر (USDT)\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 برای تهیه اشتراک:\n\n"
            f"1️⃣ به آیدی زیر پیام دهید:\n"
            f"   🆔 @{settings.SUPPORT_ID}\n\n"
            f"2️⃣ قیمت اشتراک را پرداخت کنید\n\n"
            f"3️⃣ بعد از پرداخت، دسترسی شما فعال میشود\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🆔 پشتیبانی: @{settings.SUPPORT_ID}\n\n"
            f"⚠️ توجه:\n"
            f"• اشتراک مادام‌العمر است\n"
            f"• یکبار پرداخت، استفاده همیشگی",
            reply_markup=subscription_keyboard(),
            parse_mode="HTML"
        )

@router.message(Command("backtest"))
async def backtest_command(message: Message):
    """دستور بک‌تست - فقط برای ادمین"""
    user_id = message.from_user.id
    
    # فقط ادمین مجاز است
    if user_id != settings.ADMIN_ID:
        await message.answer("⛔ شما دسترسی به این بخش ندارید.")
        return
    
    # چک عضویت
    if not await check_membership(user_id):
        await message.answer("❌ شما عضو کانال نیستید.")
        return
    
    await message.answer(
        "📊 <b>بک‌تست ربات</b>\n\n"
        "لطفاً بازه زمانی مورد نظر را انتخاب کنید:\n\n"
        "• ۳ ماهه: تست کوتاه‌مدت\n"
        "• ۶ ماهه: تست میان‌مدت\n"
        "• ۱ ساله: تست بلندمدت\n"
        "• ۲ ساله: تست کامل (پیشنهادی)",
        parse_mode="HTML",
        reply_markup=backtest_keyboard()
    )

# === کالبک‌های بک‌تست ===
@router.callback_query(F.data.startswith("backtest_"))
async def handle_backtest(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    # فقط ادمین
    if user_id != settings.ADMIN_ID:
        await callback.answer("⛔ دسترسی غیرمجاز!", show_alert=True)
        return
    
    # استخراج بازه زمانی
    period_map = {
        "backtest_3m": 90,
        "backtest_6m": 180,
        "backtest_1y": 365,
        "backtest_2y": 730
    }
    
    days = period_map.get(callback.data, 730)
    period_text = {
        "backtest_3m": "۳ ماهه",
        "backtest_6m": "۶ ماهه",
        "backtest_1y": "۱ ساله",
        "backtest_2y": "۲ ساله"
    }.get(callback.data, "۲ ساله")
    
    # پیام پردازش
    await callback.message.edit_text(
        f"⏳ در حال اجرای بک‌تست {period_text}...\n"
        f"📊 نماد: BTCUSDT\n"
        f"⏰ تایم‌فریم: ۱ ساعته\n\n"
        f"لطفاً چند لحظه صبر کنید ⏳"
    )
    
    try:
        # دریافت داده از بایننس
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df = binance_service.get_klines_range("BTCUSDT", "1H", start_date, end_date)
        
        if df is None or df.empty:
            await callback.message.edit_text("❌ خطا در دریافت داده از بایننس.")
            return
        
        # محاسبه اندیکاتورها
        indicator_calc = IndicatorCalculator(df)
        indicators = indicator_calc.calculate_all_indicators()
        
        # اجرای بک‌تست
        backtest = BacktestEngine(df, initial_balance=10000)
        metrics = backtest.run(signal_generator, indicator_calc)
        
        # تولید گزارش
        report = backtest.format_report(metrics, "BTCUSDT", "1H", period_text)
        
        await callback.message.edit_text(report, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        await callback.message.edit_text(
            f"❌ خطا در اجرای بک‌تست:\n{str(e)}\n\nلطفاً دوباره تلاش کنید."
        )

@router.callback_query(F.data == "check_membership")
async def check_membership_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_member = await check_membership(user_id)
    
    if is_member:
        await callback.message.edit_text(
            "✅ عضویت شما تایید شد! 🎉\n\n"
            "تبریک! اشتراک شما فعال است.\n\n"
            "📸 حالا میتوانید عکس چارت را بفرستید."
        )
    else:
        await callback.message.edit_text(
            "❌ شما هنوز عضو کانال خصوصی نیستید.\n\n"
            f"📌 برای تهیه اشتراک:\n\n"
            f"1️⃣ به آیدی زیر پیام دهید:\n"
            f"   🆔 @{settings.SUPPORT_ID}\n\n"
            f"2️⃣ قیمت اشتراک را پرداخت کنید\n\n"
            f"3️⃣ پس از پرداخت، عضویت شما فعال میشود\n\n"
            f"💎 قیمت اشتراک: {settings.SUBSCRIPTION_PRICE} تتر (USDT)",
            reply_markup=subscription_keyboard()
        )

@router.message(F.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id
    
    # چک عضویت
    if not await check_membership(user_id):
        await message.answer(
            "❌ شما عضو کانال خصوصی نیستید.\n\n"
            f"برای تهیه اشتراک به @{settings.SUPPORT_ID} پیام دهید."
        )
        return
    
    # پیام پردازش
    processing_msg = await message.answer("⏳ در حال تحلیل تصویر و تولید بهترین سیگنال معاملاتی...\nلطفاً چند لحظه صبر کنید ⏳")
    
    try:
        # دانلود عکس
        photo = await message.photo[-1].download()
        image_bytes = photo.read()
        
        # OCR
        ocr_result = ocr_engine.extract_chart_info(image_bytes)
        if "error" in ocr_result or not ocr_result.get("symbol") or not ocr_result.get("timeframe"):
            await processing_msg.delete()
            await message.answer(
                "❌ نتونستم اطلاعات رو تشخیص بدم!\n\n"
                "لطفاً یک اسکرین‌شات با کیفیت بهتر ارسال کنید.\n\n"
                "📌 نکات:\n"
                "• عکس واضح باشد\n"
                "• نماد و قیمت در عکس دیده شود\n"
                "• از چارت TradingView یا Binance استفاده کنید"
            )
            return
        
        symbol = ocr_result["symbol"]
        timeframe = ocr_result["timeframe"]
        
        # دریافت داده از بایننس
        df = binance_service.get_klines(symbol, timeframe)
        if df is None or df.empty:
            await processing_msg.delete()
            await message.answer(f"❌ خطا در دریافت داده {symbol}\n\nلطفاً نماد معتبری ارسال کنید.")
            return
        
        # محاسبه اندیکاتورها
        indicator_calc = IndicatorCalculator(df)
        indicators = indicator_calc.calculate_all_indicators()
        
        # تولید سیگنال
        current_price = df['close'].iloc[-1]
        signal = signal_generator.generate_signal(symbol, timeframe, current_price, indicators, df)
        
        # قالب‌بندی و ارسال
        result_text = signal_generator.format_signal(signal)
        await processing_msg.delete()
        await message.answer(result_text, parse_mode="HTML")
        
        logger.info(f"Signal generated for {symbol} by user {user_id}")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.delete()
        await message.answer("❌ خطا در پردازش تصویر\n\nلطفاً دوباره تلاش کنید.")
