import csv
import time
import threading
from datetime import datetime
from binance_client import BinanceClient
import configparser

class OrderManager:
    def __init__(self):
        self.client = BinanceClient()
        self.config = configparser.ConfigParser()
        self.config.read('config.ini')
        
        # 初始化交易记录文件
        self.trade_file = 'trades.csv'
        self._init_trade_file()
        
        # 持仓状态
        self.position = None
        self.position_timer = None
        
        # 连续亏损计数和禁用状态
        self.consecutive_losses = 0
        self.disabled = False
        self.disabled_until = 0
        
    def _init_trade_file(self):
        """初始化交易记录文件"""
        try:
            with open(self.trade_file, 'x', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'symbol', 'side', 'order_id', 
                    'order_price', 'order_qty', 'exec_price', 
                    'exec_qty', 'status', 'pnl', 'fee', 'stop_profit', 
                    'stop_loss'
                ])
        except FileExistsError:
            pass
    
    def record_trade(self, order, exec_price=None, exec_qty=None, status='NEW', pnl=0, fee=0):
        """记录交易到CSV文件"""
        try:
            # 验证交易状态
            if status not in ['NEW', 'PARTIALLY_FILLED', 'FILLED', 'CANCELED', 'EXPIRED']:
                raise ValueError(f"无效的交易状态: {status}")
            
            # 记录交易详情到日志
            trade_info = {
                'timestamp': datetime.now().isoformat(),
                'symbol': order.get('symbol', self.config['trading']['symbol']),
                'side': order.get('side'),
                'orderId': order.get('orderId'),
                'price': order.get('price'),
                'origQty': order.get('origQty'),
                'exec_price': exec_price,
                'exec_qty': exec_qty,
                'status': status,
                'pnl': pnl,
                'fee': fee
            }
            print(f"记录交易: {trade_info}")
            
            # 写入CSV文件
            with open(self.trade_file, 'a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    order.get('symbol', self.config['trading']['symbol']),
                    order.get('side'),
                    order.get('orderId'),
                    order.get('price'),
                    order.get('origQty'),
                    exec_price,
                    exec_qty,
                    status,
                    pnl,
                    fee,
                    self.config['trading']['stop_profit'],
                    self.config['trading']['stop_loss']
                ])
            
            # 如果是平仓订单且有盈亏数据，检查连续亏损
            if status == 'FILLED' and order.get('side') in ['BUY', 'SELL'] and pnl is not None:
                self.check_consecutive_losses(pnl)
                
            # 记录交易日志
            with open('trades.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - 交易记录: {trade_info}\n")
                
        except Exception as e:
            error_msg = f"记录交易失败: {str(e)}"
            print(error_msg)
            # 记录错误日志
            with open('error.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {error_msg}\n")
            raise
    
    def get_position_status(self):
        """获取当前持仓状态"""
        return self.position
    
    def update_position(self, status):
        """更新持仓状态"""
        self.position = status
    
    def start_position_timer(self, callback):
        """启动持仓定时器"""
        max_hold_time = int(self.config['trading']['max_hold_time'])
        self.position_timer = threading.Timer(max_hold_time, self._check_position, [callback])
        self.position_timer.start()
    
    def cancel_position_timer(self):
        """取消持仓定时器"""
        if self.position_timer:
            self.position_timer.cancel()
            self.position_timer = None
    
    def _check_position(self, callback):
        """检查持仓并平仓"""
        # 检查是否需要平仓
        if self.position:
            print("Max hold time reached, closing position...")
            # 这里添加平仓逻辑
            callback()
            self.position = None
    
    def load_previous_trades(self):
        """服务启动时加载之前的交易记录"""
        try:
            with open(self.trade_file, 'r') as f:
                reader = csv.DictReader(f)
                trades = list(reader)
                
                # 检查是否有未平仓的持仓
                for trade in reversed(trades):
                    if trade['status'] == 'FILLED' and not trade.get('pnl'):
                        self.position = trade['side']
                        break
                
                # 检查连续亏损状态
                recent_trades = []
                for trade in reversed(trades):
                    if trade['status'] == 'FILLED' and trade.get('pnl'):
                        recent_trades.append(trade)
                        if len(recent_trades) >= int(self.config['trading']['consecutive_losses']):
                            break
                
                # 计算连续亏损次数
                self.consecutive_losses = 0
                for trade in recent_trades:
                    if float(trade.get('pnl', 0)) < 0:
                        self.consecutive_losses += 1
                    else:
                        break
                
                # 如果达到连续亏损阈值，设置禁用状态
                if self.consecutive_losses >= int(self.config['trading']['consecutive_losses']):
                    self.disabled = True
                    self.disabled_until = time.time() + int(self.config['trading']['disable_time'])
        except FileNotFoundError:
            pass
    
    def check_consecutive_losses(self, pnl):
        """检查连续亏损并更新禁用状态"""
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # 检查是否达到连续亏损阈值
        if self.consecutive_losses >= int(self.config['trading']['consecutive_losses']):
            self.disabled = True
            self.disabled_until = time.time() + int(self.config['trading']['disable_time'])
            print(f"达到连续亏损阈值({self.consecutive_losses}笔)，交易功能已禁用{self.config['trading']['disable_time']}秒")
    
    def restore_status(self):
        """恢复交易状态"""
        self.load_previous_trades()
        
        # 检查禁用状态是否过期
        if self.disabled and time.time() > self.disabled_until:
            self.disabled = False
            print("禁用状态已过期，交易功能已恢复")
        
        return {
            'position': self.position,
            'disabled': self.disabled,
            'disabled_until': self.disabled_until if self.disabled else None,
            'consecutive_losses': self.consecutive_losses
        }
    
    def get_current_price(self):
        """通过币安API获取当前价格"""
        symbol = self.config['trading']['symbol']
        try:
            ticker = self.client.get_current_price(symbol=symbol)
            return float(ticker['lastPrice'])
        except Exception as e:
            print(f"Error getting price: {str(e)}")
            return None
            
    def get_recent_trades(self, limit=10):
        """获取最近的交易记录"""
        try:
            with open(self.trade_file, 'r') as f:
                reader = csv.DictReader(f)
                trades = list(reader)
                return trades[-limit:]
        except FileNotFoundError:
            return []