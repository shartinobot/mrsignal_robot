"""
ربات تحلیلگر ارز دیجیتال - نسخه یکپارچه
همه کدها در یک فایل
"""

import asyncio
import logging
import sys
import os
import re
import requests
import cv2
import numpy as np
import pandas as pd
import pandas_ta as ta
import easyocr
from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import json

# ============================================
# تنظیمات لاگ
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================
# تنظیمات
# ============================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SUPPORT_ID = os.getenv("SUPPORT_ID", "support")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@channel")
SUBSCRIPTION_PRICE = os.getenv("SUBSCRIPTION_PRICE", "25")
CURRENCY = os.getenv("CURRENCY", "USDT")
BINANCE_BASE_URL = "https://api.binance.com"

# ایجاد پوشه‌های موقت
os.makedirs('/tmp/torch_cache', exist_ok=True)
os.makedirs('/tmp/easyocr_models', exist_ok=True)
os.environ['TORCH_HOME'] = '/tmp/torch_cache'

# ============================================
# وب‌سرور فیک برای جلوگیری از خاموش شدن Render
# ============================================
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'alive', 'service': 'crypto-signal-bot'}
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_web_server(port=8080):
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"🌐 Web server running on port {port}")

# ============================================
# سرویس بایننس
# ============================================
class BinanceService:
    def __init__(self):
        self.session = requests.Session()
    
    def get_klines(self, symbol: str, interval: str, limit: int = 300):
        try:
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            response = self.session.get(f"{BINANCE_BASE_URL}/api/v3/klines", params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['close'] = df['close'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['open'] = df['open'].astype(float)
            df['volume'] = df['volume'].astype(float)
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logger.error(f"Binance error: {e}")
            return None
    
    def get_klines_range(self, symbol: str, interval: str, start_date: datetime, end_date: datetime):
        try:
            start_ts = int(start_date.timestamp() * 1000)
            all_data = []
            current_start = start_ts
            while current_start < int(end_date.timestamp() * 1000):
                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": 1000,
                    "startTime": current_start
                }
                response = self.session.get(f"{BINANCE_BASE_URL}/api/v3/klines", params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                all_data.extend(data)
                current_start = data[-1][0] + 1
            if not all_data:
                return None
            df = pd.DataFrame(all_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            logger.error(f"Binance range error: {e}")
            return None

# ============================================
# پردازش تصویر و OCR
# ============================================
class ImageProcessor:
    @staticmethod
    def preprocess_image(image_bytes: bytes):
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        img = cv2.resize(img, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        enhanced = clahe.apply(gray)
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        sharpened = cv2.filter2D(enhanced, -1, kernel)
        denoised = cv2.medianBlur(sharpened, 3)
        binary = cv2.adaptiveThreshold(denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
        h, w = binary.shape[:2]
        roi = binary[0:int(h*0.15), 0:w]
        return roi, img

class OCREngine:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.processor = ImageProcessor()
    
    def extract_chart_info(self, image_bytes: bytes):
        try:
            processed_img, _ = self.processor.preprocess_image(image_bytes)
            results = self.reader.readtext(processed_img, detail=0)
            full_text = ' '.join(results)
            symbol = self._extract_symbol(full_text)
            timeframe = self._extract_timeframe(full_text)
            price = self._extract_price(full_text)
            return {"symbol": symbol, "timeframe": timeframe, "price": price}
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_symbol(self, text: str):
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'XRPUSDT']
        for s in symbols:
            if s in text:
                return s
        match = re.search(r'([A-Z]{3,6}USDT)', text)
        return match.group(1) if match else None
    
    def _extract_timeframe(self, text: str):
        tfs = ['1m','5m','15m','30m','1H','4H','1D','1W']
        for tf in tfs:
            if tf in text:
                return tf
        return None
    
    def _extract_price(self, text: str):
        match = re.search(r'(\d{1,3}(?:,\d{3})*\.\d{2})', text)
        return match.group(1).replace(',', '') if match else None

# ============================================
# تحلیل ساختار بازار
# ============================================
class MarketStructure:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.highs = df['high'].values
        self.lows = df['low'].values
    
    def analyze(self):
        peaks = self._find_peaks()
        troughs = self._find_troughs()
        trend = self._determine_trend(peaks, troughs)
        structure = self._analyze_structure(peaks, troughs)
        bos = self._detect_bos(peaks, troughs)
        choch = self._detect_choch(peaks, troughs)
        return {'trend': trend, 'structure': structure, 'bos': bos, 'choch': choch}
    
    def _find_peaks(self, window=5):
        peaks = []
        for i in range(window, len(self.highs)-window):
            if all(self.highs[i] > self.highs[i-j] for j in range(1, window+1)) and \
               all(self.highs[i] > self.highs[i+j] for j in range(1, window+1)):
                peaks.append((i, self.highs[i]))
        return peaks
    
    def _find_troughs(self, window=5):
        troughs = []
        for i in range(window, len(self.lows)-window):
            if all(self.lows[i] < self.lows[i-j] for j in range(1, window+1)) and \
               all(self.lows[i] < self.lows[i+j] for j in range(1, window+1)):
                troughs.append((i, self.lows[i]))
        return troughs
    
    def _determine_trend(self, peaks, troughs):
        if len(peaks) < 2 or len(troughs) < 2:
            return "neutral"
        bullish = peaks[-1][1] > peaks[-2][1] and troughs[-1][1] > troughs[-2][1]
        bearish = peaks[-1][1] < peaks[-2][1] and troughs[-1][1] < troughs[-2][1]
        return "bullish" if bullish else "bearish" if bearish else "neutral"
    
    def _analyze_structure(self, peaks, troughs):
        s = {'HH': False, 'HL': False, 'LH': False, 'LL': False}
        if len(peaks) >= 2:
            s['HH'] = peaks[-1][1] > peaks[-2][1]
            s['LH'] = peaks[-1][1] < peaks[-2][1]
        if len(troughs) >= 2:
            s['HL'] = troughs[-1][1] > troughs[-2][1]
            s['LL'] = troughs[-1][1] < troughs[-2][1]
        return s
    
    def _detect_bos(self, peaks, troughs):
        if len(peaks) >= 2 and peaks[-1][1] > peaks[-2][1]:
            return "bullish_bos"
        if len(troughs) >= 2 and troughs[-1][1] < troughs[-2][1]:
            return "bearish_bos"
        return "none"
    
    def _detect_choch(self, peaks, troughs):
        if len(peaks) < 3 or len(troughs) < 3:
            return "none"
        prev_bearish = peaks[-2][1] < peaks[-3][1] and troughs[-2][1] < troughs[-3][1]
        curr_bullish = peaks[-1][1] > peaks[-2][1] and troughs[-1][1] > troughs[-2][1]
        if prev_bearish and curr_bullish:
            return "bullish_choch"
        prev_bullish = peaks[-2][1] > peaks[-3][1] and troughs[-2][1] > troughs[-3][1]
        curr_bearish = peaks[-1][1] < peaks[-2][1] and troughs[-1][1] < troughs[-2][1]
        if prev_bullish and curr_bearish:
            return "bearish_choch"
        return "none"
    
    def get_score(self, analysis):
        score = 0
        if analysis['trend'] == 'bullish':
            score += 15
        elif analysis['trend'] == 'bearish':
            score -= 15
        if analysis['structure']['HH']:
            score += 10
        if analysis['structure']['HL']:
            score += 10
        if analysis['structure']['LH']:
            score -= 10
        if analysis['structure']['LL']:
            score -= 10
        if analysis['bos'] == 'bullish_bos':
            score += 15
        elif analysis['bos'] == 'bearish_bos':
            score -= 15
        if analysis['choch'] == 'bullish_choch':
            score += 20
        elif analysis['choch'] == 'bearish_choch':
            score -= 20
        return score

# ============================================
# محاسبه اندیکاتورها
# ============================================
class IndicatorCalculator:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
    
    def calculate_all_indicators(self):
        result = {}
        # RSI
        result['rsi'] = ta.rsi(self.df['close'], length=14)
        result['rsi_current'] = result['rsi'].iloc[-1] if not result['rsi'].isna().all() else None
        # MACD
        macd = ta.macd(self.df['close'])
        result['macd_line'] = macd['MACD_12_26_9']
        result['macd_signal'] = macd['MACDs_12_26_9']
        result['macd_cross'] = self._check_macd_cross(macd)
        # EMAs
        for p in [20, 50, 200]:
            result[f'ema_{p}'] = ta.ema(self.df['close'], length=p)
            result[f'ema_{p}_current'] = result[f'ema_{p}'].iloc[-1]
        # ATR
        result['atr'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        result['atr_current'] = result['atr'].iloc[-1]
        # Bollinger
        bb = ta.bbands(self.df['close'], length=20, std=2)
        result['bb_upper'] = bb['BBU_20_2.0']
        result['bb_middle'] = bb['BBM_20_2.0']
        result['bb_lower'] = bb['BBL_20_2.0']
        # SuperTrend
        st = ta.supertrend(self.df['high'], self.df['low'], self.df['close'], length=7, multiplier=3)
        result['super_trend_direction'] = st['SUPERTd_7_3.0'].iloc[-1]
        # Volume
        result['volume_sma'] = ta.sma(self.df['volume'], length=20)
        result['volume_ratio'] = self.df['volume'].iloc[-1] / result['volume_sma'].iloc[-1] if not result['volume_sma'].isna().all() else 1
        # ADX
        adx = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=14)
        result['adx_current'] = adx['ADX_14'].iloc[-1] if not adx['ADX_14'].isna().all() else 0
        # Stochastic RSI
        stoch = ta.stochrsi(self.df['close'], length=14, rsi_length=14, k=3, d=3)
        result['stoch_rsi_k'] = stoch['STOCHRSIk_14_14_3_3']
        result['stoch_rsi_d'] = stoch['STOCHRSId_14_14_3_3']
        result['stoch_rsi_cross'] = self._check_stoch_cross(result)
        # VWAP
        result['vwap'] = ta.vwap(self.df['high'], self.df['low'], self.df['close'], self.df['volume'])
        result['vwap_current'] = result['vwap'].iloc[-1]
        # Ichimoku
        ich = ta.ichimoku(self.df['high'], self.df['low'], self.df['close'])
        if ich is not None:
            ich_df = ich[0] if isinstance(ich, tuple) else ich
            if 'ITS_9' in ich_df.columns:
                result['ichimoku_signal'] = 'bullish' if ich_df['ITS_9'].iloc[-1] > ich_df['IKS_26'].iloc[-1] else 'bearish' if ich_df['ITS_9'].iloc[-1] < ich_df['IKS_26'].iloc[-1] else 'neutral'
        # OBV
        result['obv'] = ta.obv(self.df['close'], self.df['volume'])
        result['obv_trend'] = self._get_obv_trend(result)
        # CCI
        result['cci'] = ta.cci(self.df['high'], self.df['low'], self.df['close'], length=20)
        result['cci_current'] = result['cci'].iloc[-1] if not result['cci'].isna().all() else None
        # MFI
        result['mfi'] = ta.mfi(self.df['high'], self.df['low'], self.df['close'], self.df['volume'], length=14)
        result['mfi_current'] = result['mfi'].iloc[-1] if not result['mfi'].isna().all() else None
        # Donchian
        don = ta.donchian(self.df['high'], self.df['low'], lower_length=20, upper_length=20)
        result['donchian_high'] = don['DCH_20_20']
        result['donchian_low'] = don['DCL_20_20']
        # Market regime
        result['market_regime'] = self._detect_market_regime(result)
        return result
    
    def _check_macd_cross(self, macd):
        if len(macd) < 2:
            return "neutral"
        ml, sl = macd['MACD_12_26_9'], macd['MACDs_12_26_9']
        curr = ml.iloc[-1] > sl.iloc[-1]
        prev = ml.iloc[-2] > sl.iloc[-2]
        return "bullish" if curr and not prev else "bearish" if not curr and prev else "neutral"
    
    def _check_stoch_cross(self, ind):
        if 'stoch_rsi_k' not in ind:
            return "neutral"
        k, d = ind['stoch_rsi_k'].iloc[-1], ind['stoch_rsi_d'].iloc[-1]
        return "bullish" if k > d else "bearish" if k < d else "neutral"
    
    def _get_obv_trend(self, ind):
        obv = ind.get('obv')
        if obv is None or len(obv) < 20:
            return "neutral"
        sma = obv.rolling(20).mean()
        return "bullish" if obv.iloc[-1] > sma.iloc[-1] else "bearish" if obv.iloc[-1] < sma.iloc[-1] else "neutral"
    
    def _detect_market_regime(self, ind):
        adx = ind.get('adx_current', 0)
        if adx > 25:
            return "trending"
        return "ranging"

# ============================================
# تولید سیگنال
# ============================================
class SignalGenerator:
    def __init__(self):
        self.base_weights = {
            "rsi_oversold": 20, "rsi_overbought": -20,
            "macd_bullish": 20, "macd_bearish": -20,
            "ema_20_50_bullish": 15, "ema_50_200_bullish": 15,
            "super_trend_bullish": 10, "strong_volume": 10,
            "adx_strong_trend": 5, "stoch_bullish": 10,
            "ichimoku_bullish": 15, "ichimoku_bearish": -15,
            "obv_bullish": 10, "obv_bearish": -10,
            "cci_oversold": 10, "cci_overbought": -10,
            "mfi_oversold": 10, "mfi_overbought": -10
        }
    
    def generate_signal(self, symbol: str, timeframe: str, current_price: float, indicators: dict, df: pd.DataFrame):
        regime = indicators.get('market_regime', 'ranging')
        weights = self._get_dynamic_weights(regime)
        score = 50
        reasons = []
        
        # RSI
        rsi = indicators.get('rsi_current')
        if rsi:
            if rsi < 30:
                score += weights.get('rsi_oversold', 20); reasons.append("✅ RSI اشباع فروش")
            elif rsi > 70:
                score += weights.get('rsi_overbought', -20); reasons.append("❌ RSI اشباع خرید")
        
        # MACD
        if indicators.get('macd_cross') == 'bullish':
            score += weights.get('macd_bullish', 20); reasons.append("✅ تقاطع صعودی MACD")
        elif indicators.get('macd_cross') == 'bearish':
            score += weights.get('macd_bearish', -20); reasons.append("❌ تقاطع نزولی MACD")
        
        # EMAs
        if indicators.get('ema_20_current') and indicators.get('ema_50_current'):
            if indicators['ema_20_current'] > indicators['ema_50_current']:
                score += weights.get('ema_20_50_bullish', 15); reasons.append("✅ EMA20 بالای EMA50")
        if indicators.get('ema_50_current') and indicators.get('ema_200_current'):
            if indicators['ema_50_current'] > indicators['ema_200_current']:
                score += weights.get('ema_50_200_bullish', 15); reasons.append("✅ EMA50 بالای EMA200")
        
        # SuperTrend
        if indicators.get('super_trend_direction') == 1:
            score += weights.get('super_trend_bullish', 10); reasons.append("✅ روند صعودی SuperTrend")
        
        # Volume
        if indicators.get('volume_ratio', 0) > 1.5:
            score += weights.get('strong_volume', 10); reasons.append("✅ حجم بالا")
        
        # ADX
        if indicators.get('adx_current', 0) > 25:
            score += weights.get('adx_strong_trend', 5); reasons.append("✅ روند قوی (ADX)")
        
        # Stochastic
        if indicators.get('stoch_rsi_cross') == 'bullish':
            score += weights.get('stoch_bullish', 10); reasons.append("✅ تقاطع صعودی استوکاستیک")
        
        # Ichimoku
        if indicators.get('ichimoku_signal') == 'bullish':
            score += weights.get('ichimoku_bullish', 15); reasons.append("✅ Ichimoku صعودی")
        elif indicators.get('ichimoku_signal') == 'bearish':
            score += weights.get('ichimoku_bearish', -15); reasons.append("❌ Ichimoku نزولی")
        
        # OBV
        if indicators.get('obv_trend') == 'bullish':
            score += weights.get('obv_bullish', 10); reasons.append("✅ OBV صعودی")
        elif indicators.get('obv_trend') == 'bearish':
            score += weights.get('obv_bearish', -10); reasons.append("❌ OBV نزولی")
        
        # CCI
        cci = indicators.get('cci_current')
        if cci:
            if cci < -100:
                score += weights.get('cci_oversold', 10); reasons.append("✅ CCI اشباع فروش")
            elif cci > 100:
                score += weights.get('cci_overbought', -10); reasons.append("❌ CCI اشباع خرید")
        
        # MFI
        mfi = indicators.get('mfi_current')
        if mfi:
            if mfi < 20:
                score += weights.get('mfi_oversold', 10); reasons.append("✅ MFI اشباع فروش")
            elif mfi > 80:
                score += weights.get('mfi_overbought', -10); reasons.append("❌ MFI اشباع خرید")
        
        # Market Structure
        ms = MarketStructure(df)
        struct_analysis = ms.analyze()
        struct_score = ms.get_score(struct_analysis)
        score += struct_score
        if struct_score > 0:
            reasons.append(f"✅ ساختار بازار صعودی (+{struct_score})")
        elif struct_score < 0:
            reasons.append(f"❌ ساختار بازار نزولی ({struct_score})")
        
        # Signal type
        signal_type = self._get_signal_type(score)
        atr = indicators.get('atr_current', current_price * 0.01)
        entry = current_price
        if signal_type in ['strong_buy', 'buy']:
            stop_loss = entry - (1.5 * atr)
            tp1 = entry + (2 * atr)
            tp2 = entry + (3.5 * atr)
        else:
            stop_loss = entry - (1.5 * atr)
            tp1 = entry + (2 * atr)
            tp2 = entry + (3.5 * atr)
        
        leverage = self._calculate_leverage(score, indicators)
        
        return {
            'symbol': symbol, 'timeframe': timeframe, 'signal': signal_type,
            'score': score, 'confidence': self._get_confidence(score),
            'entry': entry, 'stop_loss': stop_loss,
            'take_profit_1': tp1, 'take_profit_2': tp2,
            'risk_level': self._get_risk_level(score),
            'reasons': reasons[:7], 'leverage': leverage,
            'market_regime': regime
        }
    
    def _get_dynamic_weights(self, regime):
        w = self.base_weights.copy()
        if regime == 'trending':
            w.update({'super_trend_bullish': 20, 'ema_20_50_bullish': 25, 'ema_50_200_bullish': 25,
                      'adx_strong_trend': 15, 'ichimoku_bullish': 25, 'macd_bullish': 25,
                      'rsi_oversold': 10})
        elif regime == 'ranging':
            w.update({'rsi_oversold': 30, 'rsi_overbought': -30, 'cci_oversold': 20,
                      'cci_overbought': -20, 'stoch_bullish': 20})
        return w
    
    def _get_signal_type(self, score):
        if score >= 80: return "strong_buy"
        elif score >= 66: return "buy"
        elif score >= 51: return "neutral"
        elif score >= 31: return "sell"
        else: return "strong_sell"
    
    def _get_confidence(self, score):
        if score >= 80: return min(score + 10, 100)
        elif score <= 20: return min(abs(score - 20) + 70, 100)
        return min(score + 20, 100)
    
    def _get_risk_level(self, score):
        if score >= 80 or score <= 20: return "پایین"
        elif score >= 66 or score <= 35: return "متوسط"
        else: return "بالا"
    
    def _calculate_leverage(self, score, ind):
        base = 0
        if score >= 80: base += 3
        elif score >= 65: base += 2
        elif score >= 50: base += 1
        else: return {"recommended": 1, "max": 1, "safe": 1}
        if ind.get('volume_ratio', 0) > 1.5: base += 1
        if ind.get('adx_current', 0) > 25: base += 0.5
        if ind.get('market_regime') == 'trending': base += 0.5
        base = max(1, min(3, base))
        return {"recommended": round(base, 1), "max": min(base + 0.5, 3), "safe": max(1, base - 0.5)}
    
    def format_signal(self, signal):
        emoji = {'strong_buy': '🟢', 'buy': '🟢', 'neutral': '⚪', 'sell': '🟠', 'strong_sell': '🔴'}
        text = {'strong_buy': 'خرید قوی', 'buy': 'خرید', 'neutral': 'خنثی', 'sell': 'فروش', 'strong_sell': 'فروش قوی'}
        regime_text = {'trending': 'روندی 📈', 'ranging': 'رنج 🔄'}
        
        msg = f"{emoji[signal['signal']]} <b>سیگنال: {text[signal['signal']]}</b>\n\n"
        msg += f"📊 {signal['symbol']} - {signal['timeframe']}\n"
        msg += f"💰 قیمت: ${signal['entry']:,.2f}\n"
        msg += f"📊 وضعیت: {regime_text.get(signal['market_regime'], 'نامشخص')}\n\n"
        msg += f"🎯 <b>سطوح:</b>\n"
        msg += f"• ورود: ${signal['entry']:,.2f}\n"
        msg += f"• حد ضرر: ${signal['stop_loss']:,.2f}\n"
        msg += f"• هدف ۱: ${signal['take_profit_1']:,.2f}\n"
        msg += f"• هدف ۲: ${signal['take_profit_2']:,.2f}\n\n"
        msg += f"📈 اطمینان: {signal['confidence']}%\n"
        msg += f"🛡️ ریسک: {signal['risk_level']}\n\n"
        
        lev = signal.get('leverage', {})
        if lev:
            msg += f"⚡ اهرم پیشنهادی: {lev['recommended']}x\n"
            msg += f"   • حداکثر: {lev['max']}x | ایمن: {lev['safe']}x\n\n"
        
        if signal['reasons']:
            msg += "💡 دلایل:\n" + "\n".join(signal['reasons'][:6]) + "\n\n"
        
        msg += "⚠️ تحلیل لحظه‌ای - مسئولیت با کاربر"
        return msg

# ============================================
# ربات تلگرام (Aiogram)
# ============================================
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

# سرویس‌ها
binance = BinanceService()
ocr_engine = OCREngine()
signal_gen = SignalGenerator()

# ============================================
# توابع کمکی
# ============================================
async def check_membership(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except:
        return False

def sub_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 بررسی عضویت", callback_data="check_membership")]
    ])

def backtest_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 ۳ ماهه", callback_data="bt_3m"),
         InlineKeyboardButton(text="📊 ۶ ماهه", callback_data="bt_6m")],
        [InlineKeyboardButton(text="📊 ۱ ساله", callback_data="bt_1y"),
         InlineKeyboardButton(text="📊 ۲ ساله", callback_data="bt_2y")]
    ])

# ============================================
# بک‌تست
# ============================================
class BacktestEngine:
    def __init__(self, df, initial_balance=10000):
        self.df = df.copy()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.equity_curve = []
        self.position = 0
        self.entry_price = 0
    
    def run(self, signal_gen, ind_calc):
        for i in range(100, len(self.df)):
            slice_df = self.df.iloc[:i+1]
            ind = ind_calc.calculate_all_indicators()
            sig = signal_gen.generate_signal("BTCUSDT", "1H", self.df.iloc[i]['close'], ind, slice_df)
            
            if sig['signal'] in ['strong_buy', 'buy'] and self.position == 0:
                self.entry_price = self.df.iloc[i]['close']
                self.position = self.balance / self.entry_price
                self.balance = 0
            elif self.position > 0:
                price = self.df.iloc[i]['close']
                sl = sig.get('stop_loss', self.entry_price * 0.98)
                tp = sig.get('take_profit_1', self.entry_price * 1.02)
                if price <= sl or price >= tp:
                    self.balance = self.position * price
                    profit = (price - self.entry_price) / self.entry_price
                    self.trades.append({'profit': profit, 'result': 'win' if profit > 0 else 'loss'})
                    self.position = 0
            
            if self.position > 0:
                self.equity_curve.append(self.position * self.df.iloc[i]['close'])
            else:
                self.equity_curve.append(self.balance)
        
        return self._calc_metrics()
    
    def _calc_metrics(self):
        if not self.trades:
            return {'total_trades': 0, 'win_rate': 0, 'profit_factor': 0, 'max_drawdown': 0, 'total_return': 0}
        wins = [t for t in self.trades if t['result'] == 'win']
        losses = [t for t in self.trades if t['result'] == 'loss']
        win_rate = len(wins) / len(self.trades)
        total_profit = sum([t['profit'] for t in wins])
        total_loss = abs(sum([t['profit'] for t in losses])) if losses else 1
        eq = pd.Series(self.equity_curve)
        dd = (eq.expanding().max() - eq) / eq.expanding().max()
        return {
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': total_profit / total_loss,
            'max_drawdown': dd.max(),
            'total_return': (self.equity_curve[-1] - self.initial_balance) / self.initial_balance,
            'final_balance': self.equity_curve[-1]
        }
    
    def format_report(self, m, symbol, tf, period):
        if m['total_trades'] == 0:
            return "❌ هیچ معامله‌ای انجام نشد."
        return f"""═══════════════════════════════════════
📊 گزارش بک‌تست
═══════════════════════════════════════

📈 {symbol} - {tf} - {period}
📊 تعداد معاملات: {m['total_trades']}

✅ نرخ برد: {m['win_rate']*100:.1f}%
✅ نسبت سود/ضرر: {m['profit_factor']:.2f}
✅ بیشترین افت: {m['max_drawdown']*100:.1f}%
💰 سود کل: {m['total_return']*100:.1f}%
💰 سرمایه نهایی: ${m['final_balance']:,.2f}
═══════════════════════════════════════"""

# ============================================
# هندلرهای ربات
# ============================================
@router.message(Command("start"))
async def start_cmd(msg: Message):
    if not await check_membership(msg.from_user.id):
        await msg.answer(
            f"🤖 ربات تحلیلگر ارز دیجیتال\n\n"
            f"برای استفاده اشتراک تهیه کنید:\n"
            f"💰 {SUBSCRIPTION_PRICE} {CURRENCY}\n"
            f"🆔 @{SUPPORT_ID}\n\n"
            f"پس از پرداخت عضو کانال شوید.",
            reply_markup=sub_keyboard()
        )
    else:
        await msg.answer("✅ فعال!\n📸 عکس چارت بفرستید.\n\n⚡ /backtest برای بک‌تست")

@router.message(Command("backtest"))
async def backtest_cmd(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        await msg.answer("⛔ فقط ادمین")
        return
    if not await check_membership(msg.from_user.id):
        await msg.answer("❌ عضو کانال نیستید")
        return
    await msg.answer("📊 بازه زمانی را انتخاب کنید:", reply_markup=backtest_keyboard())

@router.callback_query(F.data.startswith("bt_"))
async def bt_callback(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("⛔", show_alert=True)
        return
    days = {"bt_3m":90, "bt_6m":180, "bt_1y":365, "bt_2y":730}.get(cb.data, 730)
    label = {"bt_3m":"۳ ماهه","bt_6m":"۶ ماهه","bt_1y":"۱ ساله","bt_2y":"۲ ساله"}.get(cb.data, "۲ ساله")
    await cb.message.edit_text(f"⏳ در حال بک‌تست {label}...")
    try:
        end = datetime.now()
        start = end - timedelta(days=days)
        df = binance.get_klines_range("BTCUSDT", "1H", start, end)
        if df is None or df.empty:
            await cb.message.edit_text("❌ خطا در دریافت داده")
            return
        ind_calc = IndicatorCalculator(df)
        bt = BacktestEngine(df)
        metrics = bt.run(signal_gen, ind_calc)
        report = bt.format_report(metrics, "BTCUSDT", "1H", label)
        await cb.message.edit_text(report)
    except Exception as e:
        await cb.message.edit_text(f"❌ خطا: {e}")

@router.callback_query(F.data == "check_membership")
async def check_cb(cb: CallbackQuery):
    if await check_membership(cb.from_user.id):
        await cb.message.edit_text("✅ عضویت تایید شد! عکس بفرستید.")
    else:
        await cb.message.edit_text(f"❌ عضو نیستید.\n🆔 @{SUPPORT_ID}", reply_markup=sub_keyboard())

@router.message(F.photo)
async def photo_handler(msg: Message):
    if not await check_membership(msg.from_user.id):
        await msg.answer(f"❌ عضو کانال نیستید.\n🆔 @{SUPPORT_ID}")
        return
    
    proc = await msg.answer("⏳ در حال تحلیل...")
    try:
        photo = await msg.photo[-1].download()
        img_bytes = photo.read()
        ocr_result = ocr_engine.extract_chart_info(img_bytes)
        if not ocr_result.get("symbol") or not ocr_result.get("timeframe"):
            await proc.delete()
            await msg.answer("❌ تشخیص داده نشد. عکس واضح‌تر بفرستید.")
            return
        symbol = ocr_result["symbol"]
        tf = ocr_result["timeframe"]
        df = binance.get_klines(symbol, tf)
        if df is None or df.empty:
            await proc.delete()
            await msg.answer(f"❌ داده‌ای برای {symbol} موجود نیست")
            return
        ind = IndicatorCalculator(df).calculate_all_indicators()
        current_price = df['close'].iloc[-1]
        signal = signal_gen.generate_signal(symbol, tf, current_price, ind, df)
        await proc.delete()
        await msg.answer(signal_gen.format_signal(signal), parse_mode="HTML")
    except Exception as e:
        await proc.delete()
        await msg.answer(f"❌ خطا: {e}")

# ============================================
# اجرای اصلی
# ============================================
async def main():
    logger.info("🤖 Starting bot...")
    start_web_server(8080)
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Stopped")
    except Exception as e:
        logger.error(f"💥 {e}")
        sys.exit(1)
