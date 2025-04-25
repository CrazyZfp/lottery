import json
import logging.config
import os
import time

from flask import Flask, render_template, request, jsonify

from order_manager import OrderManager
from binance_client import BinanceClient
from strategy import create_strategy
from config.config_manager import app_config, override_config

# ------------------ 初始化日志配置 ------------------
if not os.path.exists("logs"):
    os.makedirs("logs")

logging_json_file = os.environ.get("LOG_FILE", "logging.json")
if os.path.exists(logging_json_file):
    with open(logging_json_file, "rt", encoding="utf-8") as f:
        logging.config.dictConfig(json.load(f))
# ---------------------------------------------------

logger = logging.getLogger(__name__)

# 初始化OrderManager实例
order_manager : OrderManager = None
binance_client: BinanceClient = None

# 全局变量存储交易状态
trade_status = {
    "position": None,  # 当前持仓方向
    "balance": float(app_config["trading"]["initial_balance"]),  # 剩余资金
    "disabled": False,  # 接口是否禁用
    "consecutive_losses": 0,  # 连续亏损次数
    "auto_trading": False,  # 自动交易状态
}

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/api/quick_order", methods=["POST"])
def quick_order():
    # 获取请求参数
    data = request.json
    opr = data.get("opr")

    # 检查参数
    if not opr or opr not in ["LONG", "SHORT", "CLOSE"]:
        return jsonify({"status": "error", "message": "无效的交易操作"})

    # 检查是否被禁用
    if trade_status["disabled"]:
        current_time = time.time()
        if current_time < order_manager.disabled_until:
            remaining_time = int(order_manager.disabled_until - current_time)
            return jsonify(
                {
                    "status": "error",
                    "message": f"交易功能已被禁用，剩余时间: {remaining_time}秒",
                }
            )
        else:
            # 解除禁用
            trade_status["disabled"] = False
            order_manager.disabled = False

    # 如果是平仓操作
    if opr == "CLOSE":
        if not trade_status["position"]:
            return jsonify({"status": "error", "message": "当前没有持仓"})

        try:
            # 市价平仓
            close_side = "SELL" if trade_status["position"] == "LONG" else "BUY"
            order = binance_client.market_order(close_side, trade_status["position"], True)

            # 取消定时器
            order_manager.cancel_position_timer()

            # 更新状态
            trade_status["position"] = None
            order_manager.update_position(None)

            # 记录交易
            current_price = binance_client.get_current_price()
            order_manager.record_trade(
                order, current_price, order.get("executedQty"), "FILLED"
            )

            return jsonify({"status": "success", "message": "平仓成功"})
        except Exception as e:
            return jsonify({"status": "error", "message": f"平仓失败: {str(e)}"})

    # 开仓操作
    # 检查是否已有持仓
    if trade_status["position"]:
        return jsonify({"status": "error", "message": "已有持仓，请先平仓"})

    try:
        # 计算开仓数量
        position_percent = app_config.getfloat("trading", "position_percent")
        leverage = app_config.getint("trading", "leverage")

        # 获取当前价格
        current_price = binance_client.get_current_price()

        # 计算开仓数量 (USDT金额 * 杠杆 * 百分比 / 当前价格)
        amount = (
            trade_status["balance"]
            * leverage
            * (position_percent / 100)
            / current_price
        )
        # 四舍五入到合适的精度
        amount = round(amount, 3)

        side = 'BUY' if opr == 'LONG' else 'SELL'
        position_side = opr

        # 市价开仓
        order = binance_client.market_order(side, position_side, amount)

        # 记录交易
        order_manager.record_trade(order, current_price, amount, "FILLED")

        # 更新持仓状态
        trade_status["position"] = position_side
        order_manager.update_position(position_side)

        # 创建止盈止损订单
        stop_profit_percent = app_config.getfloat("trading", "stop_profit")
        stop_loss_percent = app_config.getfloat("trading", "stop_loss")

        # 计算止盈止损价格
        if opr == "LONG":
            stop_profit_price = current_price * (1 + stop_profit_percent / 100)
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)
            stop_side = "SELL"
        else:  # SELL
            stop_profit_price = current_price * (1 - stop_profit_percent / 100)
            stop_loss_price = current_price * (1 + stop_loss_percent / 100)
            stop_side = "BUY"

        # 创建止盈订单
        stop_profit_order = binance_client.stop_order(
            stop_side, position_side, stop_profit_price, True
        )
        order_manager.record_trade(stop_profit_order, None, None, "NEW")

        # 创建止损订单
        stop_loss_order = binance_client.stop_order(
            stop_side, position_side, stop_loss_price, True
        )
        order_manager.record_trade(stop_loss_order, None, None, "NEW")

        # 启动持仓定时器
        order_manager.start_position_timer(lambda: close_position_callback(side))

        return jsonify({"status": "success", "message": f"{side}开仓成功"})
    except Exception as e:
        logger.error(f"{side}订单异常: {str(e)}", exc_info=e)
        return jsonify({"status": "error", "message": f"开仓失败: {str(e)}"})


# 平仓回调函数
def close_position_callback(position_side):
    if not position_side:
        return

    try:
        # 市价平仓
        close_side = "BUY" if position_side == "SELL" else "SELL"
        order = binance_client.market_order(close_side, True)

        # 更新状态
        trade_status["position"] = None
        order_manager.update_position(None)

        # 记录交易
        current_price = binance_client.get_current_price()
        order_manager.record_trade(
            order, current_price, order.get("executedQty"), "FILLED"
        )

        logger.info(f"自动平仓成功: {order.get('orderId')}")
    except Exception as e:
        logger.error(f"自动平仓失败: {str(e)}", exc_info=e)


@app.route("/api/trades")
def get_trades():
    # 获取最近交易记录
    trades = order_manager.get_recent_trades()
    return jsonify(trades)


@app.route("/api/restore")
def restore_status():
    # 从OrderManager加载之前的状态
    status = order_manager.restore_status()

    # 更新全局交易状态
    trade_status["position"] = status["position"]
    trade_status["disabled"] = status["disabled"]
    if status["disabled"]:
        trade_status["disabled_until"] = status["disabled_until"]
    trade_status["consecutive_losses"] = status["consecutive_losses"]

    # 返回当前持仓状态和余额
    return jsonify(
        {
            "position": trade_status["position"],
            "balance": trade_status["balance"],
            "disabled": trade_status["disabled"],
            "disabled_until": status.get("disabled_until"),
            "consecutive_losses": status.get("consecutive_losses"),
        }
    )


@app.route("/config")
def config_page():
    # 渲染配置页面
    return render_template("config.html")


@app.route("/api/get_config")
def get_config():
    # 从config.ini读取当前配置
    config_data = {}
    for section in app_config.sections():
        config_data[section] = {}
        for option in app_config.options(section):
            config_data[section][option] = app_config.get(section, option)
    return jsonify(config_data)


@app.route("/api/save_config", methods=["POST"])
def save_config():
    try:
        # 从请求中获取配置数据
        config_data = request.json
        logger.info(f"Received config data: {config_data}")  # 添加日志

        # 确保配置数据是字典格式
        if not isinstance(config_data, dict):
            logger.error("Invalid config format received: %s", config_data)  # 添加日志
            return jsonify({"status": "error", "message": "Invalid config format"}), 400
            
        # 保存旧的交易标的
        old_symbol = app_config.get("trading", "symbol")
        
        override_config(config_data)

        # 检查交易标的是否变更，如果变更则重新初始化订阅
        new_symbol = app_config.get("trading", "symbol")
        if old_symbol != new_symbol:
            logger.info(f"交易标的已变更: {old_symbol} -> {new_symbol}，重新初始化订阅")
            binance_client.symbol = new_symbol
            binance_client.subscribe_kline(append=False)

            # 更新order_manager中的symbol
            order_manager.symbol = new_symbol
            
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Unexpected error in save_config: {str(e)}", exc_info=e)  # 添加日志
        return jsonify({"status": "error", "message": "Internal server error"}), 500


@app.route("/api/price")
def get_price():
    # 获取实时价格
    price = binance_client.get_current_price()
    return jsonify({"price": price})


@app.route("/api/position")
def get_position():
    # 获取当前持仓状态
    return jsonify(
        {"position": trade_status["position"], "balance": trade_status["balance"]}
    )


@app.route("/api/update_strategy", methods=["POST"])
def update_strategy():
    # 更新策略
    try:
        data = request.json
        strategy_name = data.get("strategy")

        if not strategy_name or strategy_name not in [
            "simple",
            "ma",
            "rsi",
            "combined",
        ]:
            return jsonify({"status": "error", "message": "无效的策略名称"})

        # 创建新策略
        global strategy
        strategy = create_strategy(strategy_name)

        # 重新注册回调函数
        binance_client.register_kline_callback(
            lambda kline_data:
            # 如果有信号且自动交易开启，调用回调函数
            strategy_callback(strategy.analyze(kline_data))
        )

        logger.info(f"策略已更新为: {strategy_name}")
        return jsonify(
            {"status": "success", "message": f"策略已更新为: {strategy_name}"}
        )
    except Exception as e:
        logger.error(f"更新策略失败: {str(e)}", exc_info=e)
        return jsonify({"status": "error", "message": f"更新策略失败: {str(e)}"})


@app.route("/api/auto_trading", methods=["POST"])
def auto_trading():
    # 更新自动交易状态
    try:
        data = request.json
        enabled = data.get("enabled", False)

        # 更新全局状态
        trade_status["auto_trading"] = enabled

        logger.info(f"自动交易状态已更新: {'启用' if enabled else '禁用'}")
        return jsonify(
            {
                "status": "success",
                "message": f"自动交易{'启用' if enabled else '禁用'}成功",
            }
        )
    except Exception as e:
        logger.error(f"更新自动交易状态失败: {str(e)}",exc_info=e)
        return jsonify(
            {"status": "error", "message": f"更新自动交易状态失败: {str(e)}"}
        )

# 策略回调函数
def strategy_callback(signal):
    """策略信号回调函数"""
    if signal and not trade_status["position"] and not trade_status["disabled"]:
        logger.info(f"收到策略信号: {signal}")
        try:
            # 自动执行交易
            if signal in ["BUY", "SELL"]:
                # 计算开仓数量
                position_percent = app_config.getfloat("trading", "position_percent")
                leverage = app_config.getint("trading", "leverage")

                # 获取当前价格
                current_price = binance_client.get_current_price()

                # 计算开仓数量
                amount = (
                    trade_status["balance"]
                    * leverage
                    * (position_percent / 100)
                    / current_price
                )
                amount = round(amount, 3)

                # 市价开仓
                order = binance_client.market_order(signal, amount)

                # 记录交易
                order_manager.record_trade(order, current_price, amount, "FILLED")

                # 更新持仓状态
                trade_status["position"] = signal
                order_manager.update_position(signal)

                # 创建止盈止损订单
                stop_profit_percent = app_config.getfloat("trading", "stop_profit")
                stop_loss_percent = app_config.getfloat("trading", "stop_loss")

                # 计算止盈止损价格
                if signal == "BUY":
                    stop_profit_price = current_price * (
                        1 + stop_profit_percent / 100
                    )
                    stop_loss_price = current_price * (1 - stop_loss_percent / 100)
                    stop_profit_side = "SELL"
                    stop_loss_side = "SELL"
                else:  # SELL
                    stop_profit_price = current_price * (
                        1 - stop_profit_percent / 100
                    )
                    stop_loss_price = current_price * (1 + stop_loss_percent / 100)
                    stop_profit_side = "BUY"
                    stop_loss_side = "BUY"

                # 创建止盈订单
                stop_profit_order = binance_client.stop_order(
                    stop_profit_side, stop_profit_price, True
                )
                order_manager.record_trade(stop_profit_order, None, None, "NEW")

                # 创建止损订单
                stop_loss_order = binance_client.stop_order(
                    stop_loss_side, stop_loss_price, True
                )
                order_manager.record_trade(stop_loss_order, None, None, "NEW")

                # 启动持仓定时器
                order_manager.start_position_timer(
                    lambda: close_position_callback(signal)
                )

                logger.info(f"策略自动开仓成功: {signal}")
        except Exception as e:
            logger.error(f"策略自动开仓失败: {str(e)}", exc_info=e)

def init_app():
    global order_manager, binance_client
    binance_client = BinanceClient()
    binance_client.refresh_exchange_info()
    
    order_manager = OrderManager(binance_client)

    # 服务启动时恢复交易状态
    status = order_manager.restore_status()
    trade_status["position"] = status["position"]
    trade_status["disabled"] = status["disabled"]
    if status["disabled"]:
        trade_status["disabled_until"] = status["disabled_until"]
    trade_status["consecutive_losses"] = status["consecutive_losses"]

    # 初始化策略
    strategy = create_strategy()

    # 将回调函数注册到BinanceClient
    binance_client.register_kline_callback(
        lambda kline_data:
        # 分析K线数据并生成信号
        strategy_callback(strategy.analyze(kline_data))
    )

    logger.info(
        f"服务启动成功，当前状态: 持仓={trade_status['position']}, 禁用={trade_status['disabled']}"
    )

if __name__ == "__main__":
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        init_app()
    app.run(debug=True, port=5000, host="127.0.0.1")
