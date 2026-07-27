from typing import Dict, Any
import pandas as pd
from analysis.market_structure import MarketStructure

class SignalGenerator:
    def __init__(self):
        self.base_weights = {
            "rsi_oversold": 20, "rsi_overbought": -20,
            "macd_bullish": 20, "macd_bearish": -20,
            "ema_20_50_bullish": 15, "ema_50_200_bullish": 15,
            "price_near_support": 15, "strong_volume": 10,
            "adx_strong_trend": 5, "super_trend_bullish": 10,
            "stoch_bullish": 10,
            # جدید
            "ichimoku_bullish": 15, "ichimoku_bearish": -15,
            "obv_bullish": 10, "obv_bearish": -10,
            "cci_oversold": 10, "cci_overbought": -10,
            "mfi_oversold": 10, "mfi_overbought": -10,
            "donchian_oversold": 10, "donchian_overbought": -10,
            "cmf_bullish": 10, "cmf_bearish": -10,
            "market_structure": 20  # از Market Structure
        }
    
    def generate_signal(self, symbol: str, timeframe: str, 
                        current_price: float, indicators: Dict, 
                        df: pd.DataFrame) -> Dict:
        """تولید سیگنال با امتیازدهی پویا"""
        
        # تشخیص وضعیت بازار
        market_regime = indicators.get('market_regime', 'ranging')
        
        # تنظیم وزن‌ها بر اساس وضعیت بازار (امتیازدهی پویا)
        weights = self._get_dynamic_weights(market_regime)
        
        score = 50  # شروع از خنثی
        reasons = []
        
        # === اندیکاتورهای قبلی ===
        # RSI
        rsi = indicators.get('rsi_current')
        if rsi:
            if rsi < 30:
                score += weights.get('rsi_oversold', 20)
                reasons.append("✅ RSI اشباع فروش")
            elif rsi > 70:
                score += weights.get('rsi_overbought', -20)
                reasons.append("❌ RSI اشباع خرید")
        
        # MACD
        if indicators.get('macd_cross') == 'bullish':
            score += weights.get('macd_bullish', 20)
            reasons.append("✅ تقاطع صعودی MACD")
        elif indicators.get('macd_cross') == 'bearish':
            score += weights.get('macd_bearish', -20)
            reasons.append("❌ تقاطع نزولی MACD")
        
        # EMAs
        ema_20 = indicators.get('ema_20_current')
        ema_50 = indicators.get('ema_50_current')
        ema_200 = indicators.get('ema_200_current')
        if ema_20 and ema_50 and ema_20 > ema_50:
            score += weights.get('ema_20_50_bullish', 15)
            reasons.append("✅ EMA20 بالای EMA50")
        if ema_50 and ema_200 and ema_50 > ema_200:
            score += weights.get('ema_50_200_bullish', 15)
            reasons.append("✅ EMA50 بالای EMA200")
        
        # SuperTrend
        if indicators.get('super_trend_direction') == 1:
            score += weights.get('super_trend_bullish', 10)
            reasons.append("✅ روند صعودی SuperTrend")
        
        # Volume
        volume_ratio = indicators.get('volume_ratio', 1)
        if volume_ratio > 1.5:
            score += weights.get('strong_volume', 10)
            reasons.append("✅ حجم بالا")
        
        # ADX
        if indicators.get('adx_current', 0) > 25:
            score += weights.get('adx_strong_trend', 5)
            reasons.append("✅ روند قوی (ADX)")
        
        # Stochastic
        if indicators.get('stoch_rsi_cross') == 'bullish':
            score += weights.get('stoch_bullish', 10)
            reasons.append("✅ تقاطع صعودی استوکاستیک")
        
        # === اندیکاتورهای جدید ===
        
        # 1. Ichimoku
        if indicators.get('ichimoku_signal') == 'bullish':
            score += weights.get('ichimoku_bullish', 15)
            reasons.append("✅ Ichimoku صعودی")
        elif indicators.get('ichimoku_signal') == 'bearish':
            score += weights.get('ichimoku_bearish', -15)
            reasons.append("❌ Ichimoku نزولی")
        
        # 2. OBV
        if indicators.get('obv_trend') == 'bullish':
            score += weights.get('obv_bullish', 10)
            reasons.append("✅ OBV صعودی")
        elif indicators.get('obv_trend') == 'bearish':
            score += weights.get('obv_bearish', -10)
            reasons.append("❌ OBV نزولی")
        
        # 3. CCI
        cci = indicators.get('cci_current')
        if cci:
            if cci < -100:
                score += weights.get('cci_oversold', 10)
                reasons.append("✅ CCI اشباع فروش")
            elif cci > 100:
                score += weights.get('cci_overbought', -10)
                reasons.append("❌ CCI اشباع خرید")
        
        # 4. MFI
        mfi = indicators.get('mfi_current')
        if mfi:
            if mfi < 20:
                score += weights.get('mfi_oversold', 10)
                reasons.append("✅ MFI اشباع فروش")
            elif mfi > 80:
                score += weights.get('mfi_overbought', -10)
                reasons.append("❌ MFI اشباع خرید")
        
        # 5. Donchian
        if indicators.get('donchian_position') == 'oversold':
            score += weights.get('donchian_oversold', 10)
            reasons.append("✅ قیمت در کف کانال Donchian")
        elif indicators.get('donchian_position') == 'overbought':
            score += weights.get('donchian_overbought', -10)
            reasons.append("❌ قیمت در سقف کانال Donchian")
        
        # 6. CMF
        cmf = indicators.get('cmf_current')
        if cmf:
            if cmf > 0.1:
                score += weights.get('cmf_bullish', 10)
                reasons.append("✅ جریان پول مثبت (CMF)")
            elif cmf < -0.1:
                score += weights.get('cmf_bearish', -10)
                reasons.append("❌ جریان پول منفی (CMF)")
        
        # === تحلیل ساختار بازار ===
        market_struct = MarketStructure(df)
        structure_analysis = market_struct.analyze()
        structure_score = market_struct.get_score(structure_analysis)
        
        score += structure_score
        if structure_score > 0:
            reasons.append(f"✅ ساختار بازار صعودی (+{structure_score})")
        elif structure_score < 0:
            reasons.append(f"❌ ساختار بازار نزولی ({structure_score})")
        
        # === اعمال فیلترها ===
        # فیلتر اخبار (ساده شده)
        # می‌تواند با API اخبار واقعی جایگزین شود
        news_filter = self._check_news_filter()
        if not news_filter:
            score = 50  # خنثی
            reasons.append("⏸️ زمان انتشار اخبار مهم - معامله غیرفعال")
        
        # === محاسبه سطوح ===
        atr = indicators.get('atr_current', current_price * 0.01)
        entry = current_price
        signal_type = self._get_signal_type(score)
        
        if signal_type in ['strong_buy', 'buy']:
            stop_loss = entry - (1.5 * atr)
            take_profit_1 = entry + (2 * atr)
            take_profit_2 = entry + (3.5 * atr)
            leverage = self._calculate_leverage(score, indicators)
        elif signal_type in ['strong_sell', 'sell']:
            stop_loss = entry + (1.5 * atr)
            take_profit_1 = entry - (2 * atr)
            take_profit_2 = entry - (3.5 * atr)
            leverage = self._calculate_leverage(score, indicators)
        else:
            stop_loss = entry - (1.5 * atr)
            take_profit_1 = entry + (2 * atr)
            take_profit_2 = entry + (3.5 * atr)
            leverage = {"recommended": 1, "max": 1, "safe": 1}
        
        return {
            'symbol': symbol,
            'timeframe': timeframe,
            'signal': signal_type,
            'score': score,
            'confidence': self._get_confidence(score),
            'entry': entry,
            'stop_loss': stop_loss,
            'take_profit_1': take_profit_1,
            'take_profit_2': take_profit_2,
            'risk_level': self._get_risk_level(score),
            'reasons': reasons[:8],  # حداکثر ۸ دلیل
            'leverage': leverage,
            'market_regime': market_regime,
            'structure': structure_analysis
        }
    
    def _get_dynamic_weights(self, market_regime: str) -> Dict:
        """وزن‌های پویا بر اساس وضعیت بازار"""
        weights = self.base_weights.copy()
        
        if market_regime == 'trending':
            # در بازار روندی: اندیکاتورهای روند مهم‌تر
            weights['super_trend_bullish'] = 20
            weights['ema_20_50_bullish'] = 25
            weights['ema_50_200_bullish'] = 25
            weights['adx_strong_trend'] = 15
            weights['ichimoku_bullish'] = 25
            weights['rsi_oversold'] = 10  # کمتر مهم
            weights['macd_bullish'] = 25
            
        elif market_regime == 'ranging':
            # در بازار رنج: اندیکاتورهای برگشتی مهم‌تر
            weights['rsi_oversold'] = 30
            weights['rsi_overbought'] = -30
            weights['cci_oversold'] = 20
            weights['cci_overbought'] = -20
            weights['stoch_bullish'] = 20
            weights['donchian_oversold'] = 20
            weights['super_trend_bullish'] = 5  # کمتر مهم
            weights['ema_20_50_bullish'] = 5
            
        elif market_regime == 'compressing':
            # در فشردگی: اندیکاتورهای شکست مهم‌تر
            weights['adx_strong_trend'] = 25
            weights['volume_ratio'] = 25
            weights['ichimoku_bullish'] = 20
            weights['market_structure'] = 25
        
        return weights
    
    def _check_news_filter(self) -> bool:
        """بررسی فیلتر اخبار (ساده)"""
        # در نسخه کامل، از API اخبار واقعی استفاده می‌شود
        # فعلاً همیشه True برمی‌گرداند
        return True
    
    def _get_signal_type(self, score: int) -> str:
        if score >= 80: return "strong_buy"
        elif score >= 66: return "buy"
        elif score >= 51: return "neutral"
        elif score >= 31: return "sell"
        else: return "strong_sell"
    
    def _get_risk_level(self, score: int) -> str:
        if score >= 80 or score <= 20: return "پایین"
        elif score >= 66 or score <= 35: return "متوسط"
        else: return "بالا"
    
    def _get_confidence(self, score: int) -> int:
        if score >= 80: return min(score + 10, 100)
        elif score <= 20: return min(abs(score - 20) + 70, 100)
        return min(score + 20, 100)
    
    def _calculate_leverage(self, score: int, indicators: Dict) -> Dict:
        base = 0
        if score >= 80: base += 3
        elif score >= 65: base += 2
        elif score >= 50: base += 1
        else: return {"recommended": 1, "max": 1, "safe": 1}
        
        if indicators.get('volume_ratio', 1) > 1.5: base += 1
        if indicators.get('adx_current', 0) > 25: base += 0.5
        
        # بررسی وضعیت بازار
        if indicators.get('market_regime') == 'trending':
            base += 0.5
        elif indicators.get('market_regime') == 'ranging':
            base -= 0.5
        
        # محدود کردن
        base = max(1, min(3, base))
        
        return {
            "recommended": round(base, 1),
            "max": min(base + 0.5, 3),
            "safe": max(1, base - 0.5)
        }
    
    def format_signal(self, signal: Dict) -> str:
        """قالب‌بندی سیگنال"""
        emoji = {'strong_buy': '🟢', 'buy': '🟢', 'neutral': '⚪', 'sell': '🟠', 'strong_sell': '🔴'}
        text = {'strong_buy': 'خرید قوی', 'buy': 'خرید', 'neutral': 'خنثی', 'sell': 'فروش', 'strong_sell': 'فروش قوی'}
        
        msg = f"{emoji[signal['signal']]} <b>سیگنال: {text[signal['signal']]}</b>\n\n"
        msg += f"📊 {signal['symbol']} - تایم‌فریم {signal['timeframe']}\n"
        msg += f"💰 قیمت فعلی: ${signal['entry']:,.2f}\n"
        
        # وضعیت بازار
        regime = signal.get('market_regime', 'نامشخص')
        regime_text = {'trending': 'روندی 📈', 'ranging': 'رنج 🔄', 'compressing': 'فشردگی ⏳'}
        msg += f"📊 وضعیت بازار: {regime_text.get(regime, regime)}\n\n"
        
        msg += f"🎯 <b>سطوح معاملاتی:</b>\n"
        msg += f"• ورود: ${signal['entry']:,.2f}\n"
        msg += f"• حد ضرر: ${signal['stop_loss']:,.2f}\n"
        msg += f"• هدف ۱: ${signal['take_profit_1']:,.2f}\n"
        msg += f"• هدف ۲: ${signal['take_profit_2']:,.2f}\n\n"
        
        msg += f"📈 <b>اطمینان:</b> {signal['confidence']}%\n"
        msg += f"🛡️ <b>ریسک:</b> {signal['risk_level']}\n\n"
        
        # اهرم
        lev = signal.get('leverage', {})
        if lev:
            msg += f"⚡ <b>پیشنهاد اهرم:</b> {lev['recommended']}x\n"
            msg += f"   • حداکثر مجاز: {lev['max']}x\n"
            msg += f"   • اهرم ایمن: {lev['safe']}x\n\n"
        
        # دلایل
        if signal['reasons']:
            msg += f"💡 <b>دلایل سیگنال:</b>\n"
            for r in signal['reasons'][:7]:
                msg += f"{r}\n"
        
        msg += f"\n⚠️ <i>تحلیل لحظه‌ای - مسئولیت با کاربر</i>"
        return msg
