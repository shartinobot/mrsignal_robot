import easyocr
import re
from typing import Dict, Optional
from ocr.image_processor import ImageProcessor

class OCREngine:
    def __init__(self):
        self.reader = easyocr.Reader(['en'], gpu=False)
        self.processor = ImageProcessor()
    
    def extract_chart_info(self, image_bytes: bytes) -> Dict[str, str]:
        try:
            processed_img, _ = self.processor.preprocess_image(image_bytes)
            results = self.reader.readtext(processed_img, detail=0)
            full_text = ' '.join(results)
            
            symbol = self._extract_symbol(full_text)
            timeframe = self._extract_timeframe(full_text)
            price = self._extract_price(full_text)
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "price": price,
                "raw_text": full_text
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _extract_symbol(self, text: str) -> Optional[str]:
        symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT', 
                   'DOTUSDT', 'DOGEUSDT', 'XRPUSDT', 'LINKUSDT']
        for symbol in symbols:
            if symbol in text:
                return symbol
        pattern = r'\b([A-Z]{3,6}USDT)\b'
        matches = re.findall(pattern, text)
        return matches[0] if matches else None
    
    def _extract_timeframe(self, text: str) -> Optional[str]:
        timeframes = ['1m', '5m', '15m', '30m', '1H', '4H', '1D', '1W', '1M']
        for tf in timeframes:
            if tf in text:
                return tf
        return None
    
    def _extract_price(self, text: str) -> Optional[str]:
        pattern = r'(\d{1,3}(?:,\d{3})*\.\d{2})'
        matches = re.findall(pattern, text)
        if matches:
            return matches[0].replace(',', '')
        return None
