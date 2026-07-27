import requests
import pandas as pd
from typing import Optional
from datetime import datetime
from config.settings import settings

class BinanceService:
    def __init__(self):
        self.base_url = settings.BINANCE_BASE_URL
        self.session = requests.Session()
    
    def get_klines(self, symbol: str, interval: str, limit: int = 300) -> Optional[pd.DataFrame]:
        # کد قبلی
        try:
            endpoint = f"{self.base_url}/api/v3/klines"
            params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
        except Exception as e:
            print(f"Error fetching data: {e}")
            return None
    
    def get_klines_range(self, symbol: str, interval: str, start_date: datetime, end_date: datetime) -> Optional[pd.DataFrame]:
        """دریافت کندل‌ها در بازه زمانی مشخص (برای بک‌تست)"""
        try:
            start_ts = int(start_date.timestamp() * 1000)
            end_ts = int(end_date.timestamp() * 1000)
            
            all_data = []
            current_start = start_ts
            
            while current_start < end_ts:
                endpoint = f"{self.base_url}/api/v3/klines"
                params = {
                    "symbol": symbol.upper(),
                    "interval": interval,
                    "limit": 1000,
                    "startTime": current_start
                }
                response = self.session.get(endpoint, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    break
                
                all_data.extend(data)
                current_start = data[-1][0] + 1  # زمان آخرین کندل + ۱ میلی‌ثانیه
            
            if not all_data:
                return None
            
            df = pd.DataFrame(all_data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['open'] = df['open'].astype(float)
            df['high'] = df['high'].astype(float)
            df['low'] = df['low'].astype(float)
            df['close'] = df['close'].astype(float)
            df['volume'] = df['volume'].astype(float)
            
            # فیلتر بر اساس بازه زمانی
            df = df[(df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)]
            
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            print(f"Error fetching range data: {e}")
            return None
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        try:
            endpoint = f"{self.base_url}/api/v3/ticker/price"
            params = {"symbol": symbol.upper()}
            response = self.session.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            return float(response.json()['price'])
        except:
            return None
