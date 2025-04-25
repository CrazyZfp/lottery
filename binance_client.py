import os

from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient
import configparser
import time
import threading
import json
from datetime import datetime


class BinanceClient:
    def __init__(self):
        # 重连计数器
        self.MAX_RECONNECT_ATTEMPTS = 3
        self.RECONNECT_DELAY = 5
        self.reconnect_count = 0

        # 订单listen_key
        self.listen_key = None
        self.listen_key_expiry_time = 0

        # ticker数据
        self.current_price_map = {}
        
        # K线回调函数
        self.kline_callback = None

        config = configparser.ConfigParser()
        config.read("config.ini")

        self.api_key = os.environ["BINANCE_API_KEY"]
        self.secret_key = os.environ["BINANCE_SECRET_KEY"]
        self.symbol = config["trading"]["symbol"]
        self.leverage = int(config["trading"]["leverage"])

        # 设置代理
        proxies = {"http": "http://localhost:7890", "https": "http://localhost:7890"}
        self.client = UMFutures(
            key=self.api_key, secret=self.secret_key, proxies=proxies
        )
        self.ws_client = UMFuturesWebsocketClient(
            proxies=proxies,
            on_error=self._handle_error,
            on_message=self._handle_message,
        )

        self.subscribe_kline()
        self.subscribe_order()
        # self.subscribe_ticker()

        # 设置合约倍率
        self.client.change_leverage(symbol=self.symbol, leverage=self.leverage)

        # 启动ping定时器
        self.ping_thread = threading.Thread(target=self._send_ping_periodically)
        self.ping_thread.daemon = True
        self.ping_thread.start()

    def _handle_message(self, ws_client, msg_str):
        """处理WebSocket消息"""
        try:
            msg = json.loads(msg_str)
            try:
                if msg["e"] == "kline":
                    self._handle_kline_message(msg)
                elif msg["e"] == "outboundAccountPosition":
                    self._handle_order_message(msg)
                elif msg["e"] == "executionReport":
                    self._handle_order_message(msg)
                else:
                    print(f"未知的消息类型: {msg['e']}")
                    # 记录未知消息类型以便后续分析
                    with open('unknown_messages.log', 'a') as f:
                        f.write(f"{datetime.now().isoformat()} - 未知消息类型: {msg_str}\n")
            except KeyError as e:
                print(f"处理消息时出错，缺少关键字段: {e}")
                # 记录错误消息
                with open('error_messages.log', 'a') as f:
                    f.write(f"{datetime.now().isoformat()} - 处理消息错误: {str(e)} - 消息内容: {msg_str}\n")
        except json.JSONDecodeError as e:
            print(f"解析WebSocket消息失败: {str(e)}")
            # 记录无法解析的消息
            with open('error_messages.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - JSON解析错误: {str(e)} - 原始消息: {msg_str[:200]}\n")
        except Exception as e:
            print(f"处理WebSocket消息时发生未知错误: {str(e)}")
            # 记录未知错误
            with open('error_messages.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()} - 未知错误: {str(e)} - 消息内容: {msg_str[:200]}\n")

    def _handle_error(self, ws_client, error):
        """处理WebSocket错误"""
        print(f"WebSocket error: {error}")
        self._reconnect()

    def _handle_kline_message(self, msg: dict):
        """处理K线消息"""
        self.current_price_map[msg.get('s')] = (msg.get('k', {}).get('c'), msg.get('E'))
        print(f"Kline data: {msg}")
        
        # 如果有注册的K线回调函数，调用它
        if hasattr(self, 'kline_callback') and self.kline_callback:
            try:
                self.kline_callback(msg)
            except Exception as e:
                print(f"执行K线回调函数时出错: {str(e)}")

    def _handle_order_message(self, msg):
        """处理订单消息"""
        print(f"Order data: {msg}")
        
        # 如果是订单执行报告
        if msg.get('e') == 'executionReport':
            order_id = msg.get('i')  # 订单ID
            order_status = msg.get('X')  # 订单状态
            symbol = msg.get('s')  # 交易对
            side = msg.get('S')  # 方向
            price = msg.get('p')  # 价格
            qty = msg.get('q')  # 数量
            exec_price = msg.get('L')  # 成交价格
            exec_qty = msg.get('l')  # 成交数量
            
            # 如果订单已成交，获取盈亏和手续费信息
            if order_status == 'FILLED':
                # 获取订单详情，包括盈亏和手续费
                try:
                    order_info = self.get_order_info(order_id, symbol)
                    pnl = order_info.get('realizedPnl', 0)
                    fee = order_info.get('commission', 0)
                    
                    # 这里可以添加回调函数，通知订单管理器更新交易记录
                    print(f"订单 {order_id} 已成交，盈亏: {pnl}, 手续费: {fee}")
                except Exception as e:
                    print(f"获取订单信息失败: {str(e)}")
        
        # 如果是账户持仓更新
        elif msg.get('e') == 'outboundAccountPosition':
            # 处理账户持仓信息
            pass

    def market_order(self, side, quantity, close_position=False):
        """
        市价下单
        :param side: BUY/SELL
        :param quantity: 下单数量
        :param close_position: 是否平仓，如果为True则忽略quantity参数
        """
        if close_position:
            return self.client.new_order(
                symbol=self.symbol, side=side, type="MARKET", closePosition=True
            )
        else:
            return self.client.new_order(
                symbol=self.symbol, side=side, type="MARKET", quantity=quantity
            )

    def stop_order(self, side, stop_price, close_position=True):
        """
        止损/止盈下单
        :param side: BUY/SELL
        :param stop_price: 触发价格
        :param close_position: 是否平仓
        """
        return self.client.new_order(
            symbol=self.symbol,
            side=side,
            type="STOP_MARKET",
            stopPrice=stop_price,
            closePosition=close_position,
        )

    def subscribe_kline(self):
        """订阅K线数据"""
        config = configparser.ConfigParser()
        config.read("config.ini")
        interval = config["websocket"]["kline_interval"]
        
        print(f"Subscribing to {self.symbol} Kline data with interval {interval}...")
        try:
            self.ws_client.kline(symbol=self.symbol, interval=interval, id=1)
        except Exception as e:
            print(f"WebSocket error: {e}")
            # self._reconnect()

    def subscribe_order(self):
        """订阅订单更新"""
        if self.listen_key is None or time.time() >= self.listen_key_expiry_time:
            self.listen_key = self.client.new_listen_key()["listenKey"]
            self.listen_key_expiry_time = time.time() + 55 * 60  # 55分钟后过期

        self.ws_client.user_data(listen_key=self.listen_key, id=2)

    def get_current_price(self, symbol=None):
        """
        获取指定交易对的ticker信息
        :param symbol: 交易对符号，如BTCUSDT，默认使用配置中的symbol
        :return: 包含最新价格等信息的字典
        """
        if symbol is None:
            symbol = self.symbol
            
        if not self.current_price_map.get(symbol):
            # 如果没有缓存的价格数据，尝试从API获取
            try:
                ticker = self.client.ticker_price(symbol=symbol)
                return float(ticker['price'])
            except Exception as e:
                raise ValueError(f"获取价格失败: {str(e)}")
        
        current_price_tp = self.current_price_map[symbol]
        if time.time() * 1000 > current_price_tp[1] + 5000:
            # 如果价格数据过期，尝试从API获取
            try:
                ticker = self.client.ticker_price(symbol=symbol)
                return float(ticker['price'])
            except Exception as e:
                raise ValueError(f"获取价格失败: {str(e)}")

        return float(current_price_tp[0])

    def _reconnect(self):
        """WebSocket重连机制"""
        if self.reconnect_count < self.MAX_RECONNECT_ATTEMPTS:
            self.reconnect_count += 1
            print(f"WebSocket断开，尝试第{self.reconnect_count}次重连，等待{self.RECONNECT_DELAY}秒...")
            time.sleep(self.RECONNECT_DELAY)
            
            try:
                # 关闭现有连接
                self.ws_client.stop()
                
                # 重新初始化WebSocket客户端
                config = configparser.ConfigParser()
                config.read("config.ini")
                proxies = {"http": "http://localhost:7890", "https": "http://localhost:7890"}
                self.ws_client = UMFuturesWebsocketClient(
                    proxies=proxies,
                    on_error=self._handle_error,
                    on_message=self._handle_message,
                )
                
                # 重新订阅
                self.subscribe_kline()
                self.subscribe_order()
                
                # 重置重连计数器
                if self.ws_client.is_alive():
                    print("WebSocket重连成功")
                    self.reconnect_count = 0
            except Exception as e:
                print(f"WebSocket重连失败: {str(e)}")
                # 递归调用自身，继续尝试重连
                self._reconnect()
        else:
            print("达到最大重连次数，WebSocket连接失败")
            # 可以在这里添加通知机制，如发送邮件或短信
    
    def get_order_info(self, order_id, symbol=None):
        """
        获取订单详情，包括盈亏和手续费信息
        :param order_id: 订单ID
        :param symbol: 交易对符号，默认使用配置中的symbol
        :return: 订单详情字典
        """
        if symbol is None:
            symbol = self.symbol
            
        try:
            # 获取订单信息
            order = self.client.get_order(symbol=symbol, orderId=order_id)
            
            # 如果订单已成交，获取盈亏和手续费信息
            if order['status'] == 'FILLED':
                # 获取交易详情
                trades = self.client.get_account_trades(symbol=symbol, orderId=order_id)
                
                # 计算总盈亏和手续费
                total_pnl = 0
                total_fee = 0
                for trade in trades:
                    total_pnl += float(trade.get('realizedPnl', 0))
                    total_fee += float(trade.get('commission', 0))
                
                order['realizedPnl'] = total_pnl
                order['commission'] = total_fee
            
            return order
        except Exception as e:
            print(f"获取订单信息失败: {str(e)}")
            return {}

    def _send_ping_periodically(self):
        """每10秒发送一次ping消息"""
        while True:
            try:
                self.ws_client.ping()
                print("Sent ping")
            except Exception as e:
                print(f"Ping error: {e}")
                # 如果ping失败，尝试重连
                self._reconnect()
            time.sleep(10)
            
    def register_kline_callback(self, callback):
        """注册K线数据回调函数
        :param callback: 回调函数，接收K线数据作为参数
        """
        self.kline_callback = callback
        print("K线回调函数注册成功")
        
    def subscribe_ticker(self):
        """订阅ticker数据"""
        try:
            self.ws_client.symbol_ticker(symbol=self.symbol, id=3)
            print(f"订阅{self.symbol} Ticker数据成功")
        except Exception as e:
            print(f"订阅Ticker数据失败: {str(e)}")
            self._reconnect()
