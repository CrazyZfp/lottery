import time
import configparser
import numpy as np
from datetime import datetime
from collections import deque

class Strategy:
    """
    策略基类，用于实现各种交易策略
    """
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        self.kline_history = deque(maxlen=100)  # 存储最近100条K线数据
        self.last_signal_time = None  # 上次发出信号的时间
        self.signal_cooldown = 300  # 信号冷却时间（秒）
        
    def add_kline(self, kline_data):
        """添加K线数据到历史记录"""
        self.kline_history.append(kline_data)
        
    def analyze(self, kline_data):
        """
        分析K线数据，返回交易信号
        :param kline_data: K线数据
        :return: 交易信号 ("BUY", "SELL", None)
        """
        # 添加到历史记录
        self.add_kline(kline_data)
        
        # 基类不实现具体策略，由子类实现
        return None
        
    def _check_cooldown(self, current_time):
        """检查信号冷却时间"""
        if self.last_signal_time is None:
            return True
            
        time_diff = (current_time - self.last_signal_time).total_seconds()
        return time_diff >= self.signal_cooldown
        
    def _update_signal_time(self, current_time):
        """更新信号发出时间"""
        self.last_signal_time = current_time


class SimpleStrategy(Strategy):
    """
    简单策略示例：根据价格变动方向生成信号
    """
    def __init__(self):
        super().__init__()
        self.last_price = None
        self.last_update_time = None
        
    def analyze(self, kline_data):
        # 调用父类方法添加K线数据
        super().analyze(kline_data)
        
        # 获取当前价格
        current_price = float(kline_data.get('k', {}).get('c'))
        current_time = datetime.fromtimestamp(kline_data.get('E', 0) / 1000)
        
        # 首次运行，记录价格并返回
        if self.last_price is None:
            self.last_price = current_price
            self.last_update_time = current_time
            return None
        
        # 计算价格变动
        price_change = current_price - self.last_price
        time_diff = (current_time - self.last_update_time).total_seconds()
        
        # 只有当时间间隔超过1分钟才考虑生成信号
        if time_diff < 60:
            return None
            
        # 检查信号冷却时间
        if not self._check_cooldown(current_time):
            return None
            
        # 更新最后价格和时间
        self.last_price = current_price
        self.last_update_time = current_time
        
        # 根据价格变动生成信号
        signal = None
        if price_change > 0:
            signal = "BUY"
        elif price_change < 0:
            signal = "SELL"
            
        # 如果有信号，更新信号时间
        if signal:
            self._update_signal_time(current_time)
            
        return signal


class MAStrategy(Strategy):
    """
    移动平均线策略：使用短期和长期移动平均线的交叉产生信号
    """
    def __init__(self, short_period=5, long_period=20):
        super().__init__()
        self.short_period = short_period  # 短期MA周期
        self.long_period = long_period    # 长期MA周期
        self.prices = deque(maxlen=max(short_period, long_period) + 10)  # 存储价格数据
        
    def analyze(self, kline_data):
        # 调用父类方法添加K线数据
        super().analyze(kline_data)
        
        # 获取当前价格和时间
        current_price = float(kline_data.get('k', {}).get('c'))
        current_time = datetime.fromtimestamp(kline_data.get('E', 0) / 1000)
        
        # 添加价格到历史记录
        self.prices.append(current_price)
        
        # 如果数据不足，返回None
        if len(self.prices) < self.long_period:
            return None
            
        # 检查信号冷却时间
        if not self._check_cooldown(current_time):
            return None
            
        # 计算短期和长期移动平均线
        short_ma = np.mean(list(self.prices)[-self.short_period:])
        long_ma = np.mean(list(self.prices)[-self.long_period:])
        
        # 获取前一个周期的MA值（如果有）
        if len(self.prices) > self.long_period + 1:
            prev_prices = list(self.prices)[-(self.long_period+1):-1]
            prev_short_ma = np.mean(prev_prices[-self.short_period:])
            prev_long_ma = np.mean(prev_prices)
            
            # 判断金叉和死叉
            if prev_short_ma <= prev_long_ma and short_ma > long_ma:
                # 金叉，买入信号
                self._update_signal_time(current_time)
                return "BUY"
            elif prev_short_ma >= prev_long_ma and short_ma < long_ma:
                # 死叉，卖出信号
                self._update_signal_time(current_time)
                return "SELL"
                
        return None


class RSIStrategy(Strategy):
    """
    RSI策略：使用相对强弱指标产生信号
    超买区域（RSI > 70）产生卖出信号
    超卖区域（RSI < 30）产生买入信号
    """
    def __init__(self, period=14, overbought=70, oversold=30):
        super().__init__()
        self.period = period  # RSI计算周期
        self.overbought = overbought  # 超买阈值
        self.oversold = oversold  # 超卖阈值
        self.prices = deque(maxlen=period + 10)  # 存储价格数据
        
    def analyze(self, kline_data):
        # 调用父类方法添加K线数据
        super().analyze(kline_data)
        
        # 获取当前价格和时间
        current_price = float(kline_data.get('k', {}).get('c'))
        current_time = datetime.fromtimestamp(kline_data.get('E', 0) / 1000)
        
        # 添加价格到历史记录
        self.prices.append(current_price)
        
        # 如果数据不足，返回None
        if len(self.prices) <= self.period:
            return None
            
        # 检查信号冷却时间
        if not self._check_cooldown(current_time):
            return None
            
        # 计算RSI
        prices = list(self.prices)
        deltas = np.diff(prices)
        seed = deltas[:self.period+1]
        up = seed[seed >= 0].sum() / self.period
        down = -seed[seed < 0].sum() / self.period
        rs = up / down if down != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        # 根据RSI值产生信号
        if rsi > self.overbought:
            # 超买区域，卖出信号
            self._update_signal_time(current_time)
            return "SELL"
        elif rsi < self.oversold:
            # 超卖区域，买入信号
            self._update_signal_time(current_time)
            return "BUY"
            
        return None


# 策略工厂，用于创建不同的策略实例
def create_strategy(strategy_name="ma"):
    if strategy_name.lower() == "simple":
        return SimpleStrategy()
    elif strategy_name.lower() == "ma":
        return MAStrategy(short_period=5, long_period=20)
    elif strategy_name.lower() == "rsi":
        return RSIStrategy(period=14, overbought=70, oversold=30)
    elif strategy_name.lower() == "combined":
        # 创建组合策略
        return CombinedStrategy()
    else:
        return Strategy()  # 默认返回基础策略（不产生信号）


class CombinedStrategy(Strategy):
    """
    组合策略：结合多个策略的信号，只有当多数策略产生相同信号时才输出
    """
    def __init__(self):
        super().__init__()
        self.strategies = [
            MAStrategy(short_period=5, long_period=20),
            RSIStrategy(period=14, overbought=70, oversold=30),
            SimpleStrategy()
        ]
        
    def analyze(self, kline_data):
        # 获取当前时间
        current_time = datetime.fromtimestamp(kline_data.get('E', 0) / 1000)
        
        # 检查信号冷却时间
        if not self._check_cooldown(current_time):
            return None
            
        # 收集各策略的信号
        signals = []
        for strategy in self.strategies:
            signal = strategy.analyze(kline_data)
            if signal:
                signals.append(signal)
                
        # 如果没有信号，返回None
        if not signals:
            return None
            
        # 统计买入和卖出信号的数量
        buy_count = signals.count("BUY")
        sell_count = signals.count("SELL")
        
        # 只有当多数策略产生相同信号时才输出
        if buy_count > sell_count and buy_count >= len(self.strategies) / 2:
            self._update_signal_time(current_time)
            return "BUY"
        elif sell_count > buy_count and sell_count >= len(self.strategies) / 2:
            self._update_signal_time(current_time)
            return "SELL"
            
        return None