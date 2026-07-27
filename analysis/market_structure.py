"""
تحلیل ساختار بازار (Market Structure)
تشخیص HH/HL/LH/LL، روند و شکست ساختار
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

class MarketStructure:
    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.highs = df['high'].values
        self.lows = df['low'].values
        self.closes = df['close'].values
        
    def analyze(self) -> Dict:
        """تحلیل کامل ساختار بازار"""
        
        # تشخیص قله‌ها و دره‌ها
        peaks = self._find_peaks()
        troughs = self._find_troughs()
        
        # تشخیص روند
        trend = self._determine_trend(peaks, troughs)
        
        # تشخیص HH/HL/LH/LL
        structure = self._analyze_structure(peaks, troughs)
        
        # تشخیص شکست ساختار (BOS)
        bos = self._detect_bos(peaks, troughs)
        
        # تشخیص تغییر شخصیت (CHOCH)
        choch = self._detect_choch(peaks, troughs)
        
        return {
            'trend': trend,
            'structure': structure,
            'bos': bos,
            'choch': choch,
            'peaks': peaks[-5:] if len(peaks) >= 5 else peaks,
            'troughs': troughs[-5:] if len(troughs) >= 5 else troughs
        }
    
    def _find_peaks(self, window: int = 5) -> List[Tuple[int, float]]:
        """تشخیص قله‌ها (Higher High)"""
        peaks = []
        for i in range(window, len(self.highs) - window):
            if all(self.highs[i] > self.highs[i-j] for j in range(1, window+1)) and \
               all(self.highs[i] > self.highs[i+j] for j in range(1, window+1)):
                peaks.append((i, self.highs[i]))
        return peaks
    
    def _find_troughs(self, window: int = 5) -> List[Tuple[int, float]]:
        """تشخیص دره‌ها (Lower Low)"""
        troughs = []
        for i in range(window, len(self.lows) - window):
            if all(self.lows[i] < self.lows[i-j] for j in range(1, window+1)) and \
               all(self.lows[i] < self.lows[i+j] for j in range(1, window+1)):
                troughs.append((i, self.lows[i]))
        return troughs
    
    def _determine_trend(self, peaks: List, troughs: List) -> str:
        """تشخیص روند"""
        if len(peaks) < 2 or len(troughs) < 2:
            return "neutral"
        
        # روند صعودی: HH و HL بالاتر
        bullish = peaks[-1][1] > peaks[-2][1] and troughs[-1][1] > troughs[-2][1]
        
        # روند نزولی: LH و LL پایین‌تر
        bearish = peaks[-1][1] < peaks[-2][1] and troughs[-1][1] < troughs[-2][1]
        
        if bullish:
            return "bullish"
        elif bearish:
            return "bearish"
        else:
            return "neutral"
    
    def _analyze_structure(self, peaks: List, troughs: List) -> Dict:
        """تشخیص HH/HL/LH/LL"""
        structure = {
            'HH': False,  # Higher High
            'HL': False,  # Higher Low
            'LH': False,  # Lower High
            'LL': False   # Lower Low
        }
        
        if len(peaks) >= 2:
            structure['HH'] = peaks[-1][1] > peaks[-2][1]
            structure['LH'] = peaks[-1][1] < peaks[-2][1]
        
        if len(troughs) >= 2:
            structure['HL'] = troughs[-1][1] > troughs[-2][1]
            structure['LL'] = troughs[-1][1] < troughs[-2][1]
        
        return structure
    
    def _detect_bos(self, peaks: List, troughs: List) -> str:
        """تشخیص شکست ساختار (Break of Structure)"""
        if len(peaks) < 2 or len(troughs) < 2:
            return "none"
        
        # BOS صعودی: شکستن سقف قبلی
        if peaks[-1][1] > peaks[-2][1]:
            return "bullish_bos"
        
        # BOS نزولی: شکستن کف قبلی
        if troughs[-1][1] < troughs[-2][1]:
            return "bearish_bos"
        
        return "none"
    
    def _detect_choch(self, peaks: List, troughs: List) -> str:
        """تشخیص تغییر شخصیت (Change of Character)"""
        if len(peaks) < 3 or len(troughs) < 3:
            return "none"
        
        # CHOCH صعودی: تغییر از نزولی به صعودی
        prev_bearish = peaks[-2][1] < peaks[-3][1] and troughs[-2][1] < troughs[-3][1]
        curr_bullish = peaks[-1][1] > peaks[-2][1] and troughs[-1][1] > troughs[-2][1]
        
        if prev_bearish and curr_bullish:
            return "bullish_choch"
        
        # CHOCH نزولی: تغییر از صعودی به نزولی
        prev_bullish = peaks[-2][1] > peaks[-3][1] and troughs[-2][1] > troughs[-3][1]
        curr_bearish = peaks[-1][1] < peaks[-2][1] and troughs[-1][1] < troughs[-2][1]
        
        if prev_bullish and curr_bearish:
            return "bearish_choch"
        
        return "none"
    
    def get_score(self, structure: Dict) -> int:
        """محاسبه امتیاز بر اساس ساختار بازار"""
        score = 0
        
        if structure.get('trend') == 'bullish':
            score += 15
        elif structure.get('trend') == 'bearish':
            score -= 15
        
        if structure.get('structure', {}).get('HH'):
            score += 10
        if structure.get('structure', {}).get('HL'):
            score += 10
        if structure.get('structure', {}).get('LH'):
            score -= 10
        if structure.get('structure', {}).get('LL'):
            score -= 10
        
        if structure.get('bos') == 'bullish_bos':
            score += 15
        elif structure.get('bos') == 'bearish_bos':
            score -= 15
        
        if structure.get('choch') == 'bullish_choch':
            score += 20
        elif structure.get('choch') == 'bearish_choch':
            score -= 20
        
        return score
