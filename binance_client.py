import os
import logging
import time
import threading
import json
from decimal import Decimal, getcontext

from binance.um_futures import UMFutures
from binance.websocket.um_futures.websocket_client import UMFuturesWebsocketClient

from config.config_manager import app_config

logger = logging.getLogger(__name__)
msg_logger = logging.getLogger("ws-msg")

getcontext().prec = 28  # 设置精度足够高，避免舍入误差

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

        self.api_key = os.environ["BINANCE_API_KEY"]
        self.secret_key = os.environ["BINANCE_SECRET_KEY"]
        self.symbol = app_config["trading"]["symbol"]
        self.leverage = app_config.getint("trading", "leverage")

        self._init_rest_client()
        self._init_wsclient()

        # 启动ping定时器
        self.ping_thread = threading.Thread(target=self._send_ping_periodically)
        self.ping_thread.daemon = True
        self.ping_thread.start()

    def refresh_exchange_info(self):
        """获取交易所信息"""

        logger.info("current position mode is: %s", self.client.get_position_mode())

        exchange_info = self.client.exchange_info()
        symbol_info = {}
        for sym in exchange_info.get("symbols", []):
            if sym.get('status') != 'TRADING':
                continue
            
            min_qty = None
            step_size= None
            tick_size = None
            for flt in sym.get("filters", []):
                if flt.get("filterType") == "MARKET_LOT_SIZE":
                    min_qty, step_size = float(flt.get("minQty")), flt.get("stepSize")
                if flt.get("filterType") == "PRICE_FILTER":
                    tick_size = flt.get("tickSize")
            symbol_info[sym.get("symbol")] = (min_qty, step_size, tick_size)

        self.symbol_info = symbol_info

    def _handle_message(self, ws_client, msg_str):
        """处理WebSocket消息"""
        try:
            msg = json.loads(msg_str)

            if "e" not in msg:
                logger.error("未定义消息类型: %s", msg_str)
                return

            if msg["e"] == "kline":
                self._handle_kline_message(msg)
            elif msg["e"] == "outboundAccountPosition":
                self._handle_order_message(msg)
            elif msg["e"] == "executionReport":
                self._handle_order_message(msg)
            else:
                logger.error(f"未知的消息类型: {msg['e']}")

        except json.JSONDecodeError as e:
            logger.error("解析WebSocket消息失败: %s", msg_str, exc_info=e)
        except Exception as e:
            logger.error("处理WebSocket消息时发生未知错误: %s", msg_str, exc_info=e)

    def _handle_error(self, ws_client, error):
        """处理WebSocket错误"""
        logger.error(f"WebSocket error: {error}")
        self._reconnect()

    def _handle_kline_message(self, msg: dict):
        """处理K线消息"""

        if msg.get("s") != self.symbol:
            logger.warning(f"K线数据不是 {self.symbol} 数据: {msg}")
            return

        self.current_price_map[msg.get("s")] = (msg.get("k", {}).get("c"), msg.get("E"))
        msg_logger.info(f"Kline data: {msg}")

        # 如果有注册的K线回调函数，调用它
        if hasattr(self, "kline_callback") and self.kline_callback:
            try:
                self.kline_callback(msg)
            except Exception as e:
                logger.error(f"执行K线回调函数时出错: {str(e)}")

    def _handle_order_message(self, msg):
        """处理订单消息"""

        # 如果是订单执行报告
        if msg.get("e") == "executionReport":
            order_id = msg.get("i")  # 订单ID
            order_status = msg.get("X")  # 订单状态
            symbol = msg.get("s")  # 交易对

            # 如果订单已成交，获取盈亏和手续费信息
            if order_status == "FILLED":
                # 获取订单详情，包括盈亏和手续费
                try:
                    order_info = self.get_order_info(order_id, symbol)
                    pnl = order_info.get("realizedPnl", 0)
                    fee = order_info.get("commission", 0)

                    # 这里可以添加回调函数，通知订单管理器更新交易记录
                    logger.info(f"订单 {order_id} 已成交，盈亏: {pnl}, 手续费: {fee}")
                except Exception as e:
                    logger.error(f"获取订单信息失败: {str(e)}")

        # 如果是账户持仓更新
        elif msg.get("e") == "outboundAccountPosition":
            # 处理账户持仓信息
            pass

    def market_order(self, side, position_side, quantity=None, close_position=False):
        """
        市价下单
        :param position_side: LONG/SHORT
        :param quantity: 下单数量
        :param close_position: 是否平仓, 如果为True则忽略quantity参数
        """
        if close_position:
            return self.client.new_order(
                symbol=self.symbol, side='SELL', type="MARKET", closePosition=True
            )
        else:
            if self.symbol not in self.symbol_info:
                raise ValueError(f"未获取到 {self.symbol} 信息, 无法执行交易")

            min_qty, step_size, tick_size = self.symbol_info[self.symbol]
            quantity = self.quantize_quantity(str(quantity), step_size)
            if quantity < min_qty:
                raise ValueError(f"{self.symbol}下单数量小于最小下单量 {min_qty}")

            resp = self.client.new_order(
                symbol=self.symbol, side=side, type="MARKET", quantity=quantity, positionSide=position_side
            )

            logger.info(f"创建开仓订单: [{self.symbol}] {position_side}, {quantity}")

            return resp

    def stop_order(self, side, position_side, stop_price, close_position=True):
        """
        止损/止盈下单
        :param position_side: LONG/SHORT
        :param stop_price: 触发价格
        :param close_position: 是否平仓
        """
        min_qty, step_size, tick_size = self.symbol_info[self.symbol]
        stop_price = self.quantize_quantity(str(stop_price), tick_size)
        return self.client.new_order(
            symbol=self.symbol,
            side=side,
            positionSide=position_side,
            type="STOP_MARKET",
            stopPrice=stop_price,
            closePosition=close_position,
        )

    def list_subscription(self) -> list[str]:
        """
        查询已订阅的流
        """
        resp =  self.ws_client.list_subscribe()
        return resp.get("result", [])

    def unsubscribe(self, stream:list[str]):
        """取消数据订阅"""
        logger.info(f"Unsubscribing from {stream} ...")
        try:
            self.ws_client.unsubscribe(stream)
        except Exception as e:
            logger.error(f"unsubscribe error: {e}", exc_info=e)

    def subscribe_kline(self, append:bool = True):
        """订阅K线数据"""
        interval = app_config["websocket"]["kline_interval"]

        logger.info(
            f"Subscribing to {self.symbol} Kline data with interval {interval}..."
        )
        try:
            if not append:
                kline_subs = list(sub for sub in self.list_subscription() if '@kline' in sub)
                self.unsubscribe(kline_subs)

            self.ws_client.kline(symbol=self.symbol, interval=interval)
        except Exception as e:
            logger.error(f"WebSocket error: {e}", exc_info=e)

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

        current_price_tp = self.current_price_map.get(symbol)

        if (not current_price_tp) or time.time() * 1000 > current_price_tp[1] + 5000:
            try:
                ticker = self.client.ticker_price(symbol=symbol)
                self.current_price_map[symbol] = (ticker["price"], time.time() * 1000)
                return float(ticker["price"])
            except Exception as e:
                logger.error(f"获取{symbol}价格失败: {str(e)}", exc_info=e)
                raise ValueError(f"获取{symbol}价格失败: {str(e)}")

        return float(current_price_tp[0])
    
    def _get_proxies(self):
        if app_config.getboolean("proxies", "enabled"):
            proxies = {"http": app_config.get("proxies", "http_proxy"), "https": app_config.get("proxies", "https_proxy")}
        else:
            proxies = None
        return proxies

    def _init_rest_client(self):
        self.client = UMFutures(
            key=self.api_key, secret=self.secret_key, proxies=self._get_proxies()
        )
        # 设置合约倍率
        self.client.change_leverage(symbol=self.symbol, leverage=self.leverage)

    def _init_wsclient(self):
        self.ws_client = UMFuturesWebsocketClient(
            proxies=self._get_proxies(),
            on_error=self._handle_error,
            on_message=self._handle_message,
        )

        # 重新订阅
        self.subscribe_kline()
        self.subscribe_order()

    def _reconnect(self):
        """WebSocket重连机制"""
        if self.reconnect_count < self.MAX_RECONNECT_ATTEMPTS:
            self.reconnect_count += 1
            logger.info(
                f"WebSocket断开，尝试第{self.reconnect_count}次重连，等待{self.RECONNECT_DELAY}秒..."
            )
            time.sleep(self.RECONNECT_DELAY)

            try:
                # 关闭现有连接
                self.ws_client.stop()

                # 重新初始化WebSocket客户端
                self._init_wsclient()

                # 重置重连计数器
                if self.ws_client.is_alive():
                    logger.info("WebSocket重连成功")
                    self.reconnect_count = 0
            except Exception as e:
                logger.error(f"WebSocket重连失败: {str(e)}", exc_info=e)
                # 递归调用自身，继续尝试重连
                self._reconnect()
        else:
            logger.error(
                f"达到最大重连次数({self.MAX_RECONNECT_ATTEMPTS})，WebSocket连接失败"
            )
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
            if order["status"] == "FILLED":
                # 获取交易详情
                trades = self.client.get_account_trades(symbol=symbol, orderId=order_id)

                # 计算总盈亏和手续费
                total_pnl = 0
                total_fee = 0
                for trade in trades:
                    total_pnl += float(trade.get("realizedPnl", 0))
                    total_fee += float(trade.get("commission", 0))

                order["realizedPnl"] = total_pnl
                order["commission"] = total_fee

            return order
        except Exception as e:
            logger.error(f"获取订单信息失败: {str(e)}", exc_info=e)
            return {}

    def _send_ping_periodically(self):
        """每10秒发送一次ping消息"""
        while True:
            try:
                self.ws_client.ping()
                msg_logger.info("Sent ping")
            except Exception as e:
                logger.error(f"Ping error: {e}", exc_info=e)
                # 如果ping失败，尝试重连
                self._reconnect()
            time.sleep(10)

    def register_kline_callback(self, callback):
        """注册K线数据回调函数
        :param callback: 回调函数，接收K线数据作为参数
        """
        self.kline_callback = callback
        logger.info("K线回调函数注册成功")

    def subscribe_ticker(self):
        """订阅ticker数据"""
        try:
            self.ws_client.symbol_ticker(symbol=self.symbol, id=3)
            logger.info(f"订阅{self.symbol} Ticker数据成功")
        except Exception as e:
            logger.error(f"订阅Ticker数据失败: {str(e)}", exc_info=e)
            self._reconnect()

    def quantize_quantity(self, quantity: float, step_size: float) -> float:
        qty = Decimal(str(quantity))
        step = Decimal(str(step_size))
        # 向下取整到步长倍数
        result = (qty // step) * step
        return float(result)