import pandas as pd
import pandas_ta as ta
from typing import Dict, Any
import numpy as np

class IndicatorCalculator:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
    
    def calculate_all_indicators(self) -> Dict[str, Any]:
        """محاسبه تمام اندیکاتورها با بهبودها"""
        result = {}
        
        # === اندیکاتورهای قبلی ===
        # RSI
        result['rsi'] = ta.rsi(self.df['close'], length=14)
        result['rsi_current'] = result['rsi'].iloc[-1] if not result['rsi'].isna().all() else None
        
        # MACD
        macd = ta.macd(self.df['close'])
        result['macd_line'] = macd['MACD_12_26_9']
        result['macd_signal'] = macd['MACDs_12_26_9']
        result['macd_histogram'] = macd['MACDh_12_26_9']
        result['macd_cross'] = self._check_macd_cross(macd)
        
        # EMAs
        for period in [20, 50, 200]:
            result[f'ema_{period}'] = ta.ema(self.df['close'], length=period)
            result[f'ema_{period}_current'] = result[f'ema_{period}'].iloc[-1]
        
        # ATR
        result['atr'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        result['atr_current'] = result['atr'].iloc[-1]
        
        # Bollinger Bands
        bb = ta.bbands(self.df['close'], length=20, std=2)
        result['bb_upper'] = bb['BBU_20_2.0']
        result['bb_middle'] = bb['BBM_20_2.0']
        result['bb_lower'] = bb['BBL_20_2.0']
        result['bb_position'] = self._get_bb_position(result)
        
        # SuperTrend
        st = ta.supertrend(self.df['high'], self.df['low'], self.df['close'], length=7, multiplier=3)
        result['super_trend'] = st['SUPERT_7_3.0']
        result['super_trend_direction'] = st['SUPERTd_7_3.0'].iloc[-1]
        
        # Volume
        result['volume_sma'] = ta.sma(self.df['volume'], length=20)
        result['volume_ratio'] = self.df['volume'].iloc[-1] / result['volume_sma'].iloc[-1] if not result['volume_sma'].isna().all() else 1
        
        # ADX
        adx = ta.adx(self.df['high'], self.df['low'], self.df['close'], length=14)
        result['adx'] = adx['ADX_14']
        result['adx_current'] = result['adx'].iloc[-1]
        
        # Stochastic RSI
        stoch = ta.stochrsi(self.df['close'], length=14, rsi_length=14, k=3, d=3)
        result['stoch_rsi_k'] = stoch['STOCHRSIk_14_14_3_3']
        result['stoch_rsi_d'] = stoch['STOCHRSId_14_14_3_3']
        result['stoch_rsi_cross'] = self._check_stoch_cross(result)
        
        # VWAP
        result['vwap'] = ta.vwap(self.df['high'], self.df['low'], self.df['close'], self.df['volume'])
        result['vwap_current'] = result['vwap'].iloc[-1]
        
        # === اندیکاتورهای جدید ===
        
        # 1. Ichimoku Cloud
        ichimoku = ta.ichimoku(self.df['high'], self.df['low'], self.df['close'])
        if ichimoku is not None and len(ichimoku) > 0:
            # استخراج داده‌های Ichimoku
            ichimoku_df = ichimoku[0] if isinstance(ichimoku, tuple) else ichimoku
            result['ichimoku_tenkan'] = ichimoku_df['ITS_9'].iloc[-1] if 'ITS_9' in ichimoku_df.columns else None
            result['ichimoku_kijun'] = ichimoku_df['IKS_26'].iloc[-1] if 'IKS_26' in ichimoku_df.columns else None
            result['ichimoku_senkou_a'] = ichimoku_df['ISS_A_26'].iloc[-1] if 'ISS_A_26' in ichimoku_df.columns else None
            result['ichimoku_senkou_b'] = ichimoku_df['ISS_B_26'].iloc[-1] if 'ISS_B_26' in ichimoku_df.columns else None
            result['ichimoku_signal'] = self._get_ichimoku_signal(result)
        
        # 2. OBV (On-Balance Volume)
        result['obv'] = ta.obv(self.df['close'], self.df['volume'])
        result['obv_current'] = result['obv'].iloc[-1] if not result['obv'].isna().all() else None
        result['obv_trend'] = self._get_obv_trend(result)
        
        # 3. CCI
        result['cci'] = ta.cci(self.df['high'], self.df['low'], self.df['close'], length=20)
        result['cci_current'] = result['cci'].iloc[-1] if not result['cci'].isna().all() else None
        
        # 4. MFI
        result['mfi'] = ta.mfi(self.df['high'], self.df['low'], self.df['close'], self.df['volume'], length=14)
        result['mfi_current'] = result['mfi'].iloc[-1] if not result['mfi'].isna().all() else None
        
        # 5. Donchian Channel
        donchian = ta.donchian(self.df['high'], self.df['low'], lower_length=20, upper_length=20)
        result['donchian_high'] = donchian['DCH_20_20']
        result['donchian_low'] = donchian['DCL_20_20']
        result['donchian_mid'] = donchian['DCM_20_20']
        result['donchian_position'] = self._get_donchian_position(result)
        
        # 6. CMF (Chaikin Money Flow)
        result['cmf'] = ta.cmf(self.df['high'], self.df['low'], self.df['close'], self.df['volume'], length=20)
        result['cmf_current'] = result['cmf'].iloc[-1] if not result['cmf'].isna().all() else None
        
        # === تشخیص وضعیت بازار ===
        result['market_regime'] = self._detect_market_regime(result)
        
        return result
    
    def _get_ichimoku_signal(self, indicators: Dict) -> str:
        """تشخیص سیگنال Ichimoku"""
        tenkan = indicators.get('ichimoku_tenkan')
        kijun = indicators.get('ichimoku_kijun')
        
        if tenkan is None or kijun is None:
            return "neutral"
        
        # تقاطع Tenkan/Kijun
        if tenkan > kijun:
            return "bullish"
        elif tenkan < kijun:
            return "bearish"
        return "neutral"
    
    def _get_obv_trend(self, indicators: Dict) -> str:
        """تشخیص روند OBV"""
        obv = indicators.get('obv')
        if obv is None or len(obv) < 20:
            return "neutral"
        
        # میانگین ۲۰ دوره
        obv_sma = obv.rolling(20).mean()
        current = obv.iloc[-1]
        sma = obv_sma.iloc[-1]
        
        if current > sma:
            return "bullish"
        elif current < sma:
            return "bearish"
        return "neutral"
    
    def _get_donchian_position(self, indicators: Dict) -> str:
        """تعیین موقعیت قیمت در کانال Donchian"""
        close = self.df['close'].iloc[-1]
        high = indicators.get('donchian_high')
        low = indicators.get('donchian_low')
        
        if high is None or low is None:
            return "neutral"
        
        high_val = high.iloc[-1]
        low_val = low.iloc[-1]
        
        if close >= high_val * 0.95:  # نزدیک به بالا
            return "overbought"
        elif close <= low_val * 1.05:  # نزدیک به پایین
            return "oversold"
        return "neutral"
    
    def _detect_market_regime(self, indicators: Dict) -> str:
        """تشخیص وضعیت بازار (روندی/رنج/نوسانی)"""
        # استفاده از ADX برای تشخیص روند
        adx = indicators.get('adx_current', 0)
        
        # استفاده از باندهای بولینگر برای تشخیص فشردگی
        bb_upper = indicators.get('bb_upper')
        bb_lower = indicators.get('bb_lower')
        bb_width = None
        
        if bb_upper is not None and bb_lower is not None:
            bb_width = (bb_upper.iloc[-1] - bb_lower.iloc[-1]) / bb_middle.iloc[-1]
        
        # تشخیص
        if adx > 25:
            return "trending"
        elif bb_width is not None and bb_width < 0.03:
            return "compressing"
        else:
            return "ranging"
    
    # === توابع کمکی ===
    def _check_macd_cross(self, macd: pd.DataFrame) -> str:
        if len(macd) < 2:
            return "neutral"
        macd_line = macd['MACD_12_26_9']
        signal_line = macd['MACDs_12_26_9']
        current = macd_line.iloc[-1] > signal_line.iloc[-1]
        previous = macd_line.iloc[-2] > signal_line.iloc[-2]
        if current and not previous:
            return "bullish"
        elif not current and previous:
            return "bearish"
        return "neutral"
    
    def _get_bb_position(self, indicators: Dict) -> str:
        close = self.df['close'].iloc[-1]
        lower = indicators['bb_lower'].iloc[-1]
        upper = indicators['bb_upper'].iloc[-1]
        if close <= lower:
            return "oversold"
        elif close >= upper:
            return "overbought"
        return "neutral"
    
    def _check_stoch_cross(self, indicators: Dict) -> str:
        if 'stoch_rsi_k' not in indicators:
            return "neutral"
        k = indicators['stoch_rsi_k'].iloc[-1]
        d = indicators['stoch_rsi_d'].iloc[-1]
        if k > d:
            return "bullish"
        elif k < d:
            return "bearish"
        return "neutral"
