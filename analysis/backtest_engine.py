"""
موتور بک‌تست برای شبیه‌سازی معاملات روی داده‌های تاریخی
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class BacktestEngine:
    def __init__(self, df: pd.DataFrame, initial_balance: float = 10000):
        self.df = df.copy()
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.trades = []
        self.equity_curve = []
        self.position = 0
        self.entry_price = 0
        self.stop_loss = 0
        self.take_profit = 0
        
    def run(self, signal_generator, indicators) -> Dict:
        """اجرای بک‌تست کامل"""
        logger.info("🚀 Starting backtest...")
        
        for i in range(100, len(self.df)):  # از کندل ۱۰۰ به بعد
            # داده‌های تا این نقطه
            data_slice = self.df.iloc[:i+1]
            
            # محاسبه اندیکاتورها
            ind = indicators.calculate_all_indicators()
            
            # تولید سیگنال
            signal = signal_generator.generate_signal(
                symbol="BTCUSDT",
                timeframe="1H",
                current_price=self.df.iloc[i]['close'],
                indicators=ind,
                df=data_slice
            )
            
            signal_type = signal.get('signal', 'neutral')
            
            # مدیریت معامله
            if signal_type in ['strong_buy', 'buy'] and self.position == 0:
                self._enter_trade(i, signal)
            elif signal_type in ['strong_sell', 'sell'] and self.position == 0:
                self._enter_trade(i, signal, short=True)
            
            # بررسی خروج
            if self.position != 0:
                self._check_exit(i)
            
            # ثبت منحنی سرمایه
            if self.position > 0:
                self.equity_curve.append(self.position * self.df.iloc[i]['close'])
            elif self.position < 0:
                self.equity_curve.append(self.position * self.df.iloc[i]['close'])
            else:
                self.equity_curve.append(self.balance)
        
        # محاسبه معیارها
        metrics = self._calculate_metrics()
        logger.info("✅ Backtest completed!")
        return metrics
    
    def _enter_trade(self, i: int, signal: Dict, short: bool = False):
        """ورود به معامله"""
        price = self.df.iloc[i]['close']
        atr = signal.get('atr_current', price * 0.01)
        
        if short:
            self.entry_price = price
            self.stop_loss = price + (1.5 * atr)
            self.take_profit = price - (3 * atr)
            self.position = -(self.balance / price)  # فروش
        else:
            self.entry_price = price
            self.stop_loss = price - (1.5 * atr)
            self.take_profit = price + (3 * atr)
            self.position = self.balance / price  # خرید
        
        self.balance = 0
        
    def _check_exit(self, i: int):
        """بررسی خروج از معامله"""
        price = self.df.iloc[i]['close']
        
        if self.position > 0:  # خرید
            if price <= self.stop_loss:
                self._close_trade(i, price, "loss")
            elif price >= self.take_profit:
                self._close_trade(i, price, "win")
        elif self.position < 0:  # فروش
            if price >= self.stop_loss:
                self._close_trade(i, price, "loss")
            elif price <= self.take_profit:
                self._close_trade(i, price, "win")
    
    def _close_trade(self, i: int, price: float, result: str):
        """بستن معامله"""
        if self.position > 0:
            self.balance = self.position * price
        elif self.position < 0:
            self.balance = abs(self.position) * (2 * self.entry_price - price)
        
        profit_pct = (price - self.entry_price) / self.entry_price
        if self.position < 0:
            profit_pct = -profit_pct
        
        self.trades.append({
            'entry': self.entry_price,
            'exit': price,
            'profit': profit_pct,
            'result': result,
            'entry_time': self.df.iloc[i]['timestamp'],
            'exit_time': self.df.iloc[i]['timestamp']
        })
        
        self.position = 0
    
    def _calculate_metrics(self) -> Dict:
        """محاسبه معیارهای آماری"""
        if not self.trades:
            return self._empty_metrics()
        
        # معاملات موفق و ناموفق
        wins = [t for t in self.trades if t['result'] == 'win']
        losses = [t for t in self.trades if t['result'] == 'loss']
        
        # نرخ برد
        win_rate = len(wins) / len(self.trades) if self.trades else 0
        
        # سود و ضرر کل
        total_profit = sum([t['profit'] for t in wins])
        total_loss = abs(sum([t['profit'] for t in losses])) if losses else 0
        
        # نسبت سود به ضرر
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # امید ریاضی (Expectancy)
        avg_win = sum([t['profit'] for t in wins]) / len(wins) if wins else 0
        avg_loss = sum([t['profit'] for t in losses]) / len(losses) if losses else 0
        expectancy = (win_rate * avg_win) - ((1 - win_rate) * abs(avg_loss)) if losses else 0
        
        # محاسبه Drawdown
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.expanding().max()
        drawdown = (running_max - equity_series) / running_max
        max_drawdown = drawdown.max()
        
        # محاسبه Sharpe Ratio (ساده شده)
        returns = equity_series.pct_change().dropna()
        sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0
        
        # سود کل
        total_return = (self.equity_curve[-1] - self.initial_balance) / self.initial_balance
        
        # میانگین مدت معامله
        avg_duration = None
        
        return {
            'total_trades': len(self.trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'expectancy': expectancy,
            'total_return': total_return,
            'final_balance': self.equity_curve[-1],
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'wins': len(wins),
            'losses': len(losses)
        }
    
    def _empty_metrics(self) -> Dict:
        """گزارش خالی در صورت عدم وجود معامله"""
        return {
            'total_trades': 0,
            'win_rate': 0,
            'profit_factor': 0,
            'max_drawdown': 0,
            'sharpe_ratio': 0,
            'expectancy': 0,
            'total_return': 0,
            'final_balance': self.initial_balance,
            'avg_win': 0,
            'avg_loss': 0,
            'wins': 0,
            'losses': 0
        }
    
    def format_report(self, metrics: Dict, symbol: str, timeframe: str, period: str) -> str:
        """قالب‌بندی گزارش بک‌تست"""
        if metrics['total_trades'] == 0:
            return "❌ هیچ معامله‌ای در بازه زمانی انتخاب شده انجام نشد."
        
        msg = f"═══════════════════════════════════════\n"
        msg += f"📊 گزارش بک‌تست کامل\n"
        msg += f"═══════════════════════════════════════\n\n"
        
        msg += f"📈 اطلاعات کلی:\n"
        msg += f"• نماد: {symbol}\n"
        msg += f"• تایم‌فریم: {timeframe}\n"
        msg += f"• دوره: {period}\n"
        msg += f"• تعداد معاملات: {metrics['total_trades']}\n\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += f"🎯 معیارهای عملکرد:\n\n"
        msg += f"✅ نرخ برد (Win Rate): {metrics['win_rate']*100:.1f}%\n"
        msg += f"✅ نسبت سود به ضرر (Profit Factor): {metrics['profit_factor']:.2f}\n"
        msg += f"✅ بیشترین افت (Max Drawdown): {metrics['max_drawdown']*100:.1f}%\n"
        msg += f"✅ نسبت شارپ (Sharpe Ratio): {metrics['sharpe_ratio']:.2f}\n"
        msg += f"✅ سود مورد انتظار (Expectancy): {metrics['expectancy']*100:.2f}%\n\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += f"📊 توزیع معاملات:\n\n"
        msg += f"🟢 معاملات موفق: {metrics['wins']} ({metrics['win_rate']*100:.1f}%)\n"
        msg += f"🔴 معاملات ناموفق: {metrics['losses']} ({(1-metrics['win_rate'])*100:.1f}%)\n\n"
        
        msg += f"💰 میانگین سود موفق: {metrics['avg_win']*100:.2f}%\n"
        msg += f"💸 میانگین ضرر ناموفق: {metrics['avg_loss']*100:.2f}%\n\n"
        
        msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        msg += f"📈 منحنی سرمایه:\n\n"
        msg += f"💰 سرمایه اولیه: ${metrics['final_balance'] / (1 + metrics['total_return']):,.2f}\n"
        msg += f"💰 سرمایه نهایی: ${metrics['final_balance']:,.2f}\n"
        msg += f"📈 سود کل: {metrics['total_return']*100:.1f}%\n\n"
        
        msg += f"═══════════════════════════════════════\n"
        msg += f"⏱️ تاریخ گزارش: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        msg += f"═══════════════════════════════════════"
        
        return msg
