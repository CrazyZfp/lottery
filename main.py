from flask import Flask, render_template, request, jsonify
import configparser
import os
import time
from order_manager import OrderManager
from strategy import create_strategy

app = Flask(__name__)

# 加载配置文件
config = configparser.ConfigParser()
config.read('config.ini')

# 初始化OrderManager实例
order_manager = OrderManager()

# 全局变量存储交易状态
trade_status = {
    'position': None,  # 当前持仓方向
    'balance': float(config['trading']['initial_balance']),  # 剩余资金
    'disabled': False,  # 接口是否禁用
    'consecutive_losses': 0,  # 连续亏损次数
    'auto_trading': False  # 自动交易状态
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/history')
def history():
    return render_template('history.html')

@app.route('/api/quick_order', methods=['POST'])
def quick_order():
    # 获取请求参数
    data = request.json
    side = data.get('side')
    
    # 检查参数
    if not side or side not in ['BUY', 'SELL', 'CLOSE']:
        return jsonify({'status': 'error', 'message': '无效的交易方向'})
    
    # 检查是否被禁用
    if trade_status['disabled']:
        current_time = time.time()
        if current_time < order_manager.disabled_until:
            remaining_time = int(order_manager.disabled_until - current_time)
            return jsonify({
                'status': 'error', 
                'message': f'交易功能已被禁用，剩余时间: {remaining_time}秒'
            })
        else:
            # 解除禁用
            trade_status['disabled'] = False
            order_manager.disabled = False
    
    # 如果是平仓操作
    if side == 'CLOSE':
        if not trade_status['position']:
            return jsonify({'status': 'error', 'message': '当前没有持仓'})
        
        try:
            # 市价平仓
            close_side = 'BUY' if trade_status['position'] == 'SELL' else 'SELL'
            order = order_manager.client.market_order(close_side, True)
            
            # 取消定时器
            order_manager.cancel_position_timer()
            
            # 更新状态
            trade_status['position'] = None
            order_manager.update_position(None)
            
            # 记录交易
            current_price = order_manager.get_current_price()
            order_manager.record_trade(order, current_price, order.get('executedQty'), 'FILLED')
            
            return jsonify({'status': 'success', 'message': '平仓成功'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'平仓失败: {str(e)}'})
    
    # 开仓操作
    # 检查是否已有持仓
    if trade_status['position']:
        return jsonify({'status': 'error', 'message': '已有持仓，请先平仓'})
    
    try:
        # 计算开仓数量
        symbol = config['trading']['symbol']
        position_percent = float(config['trading']['position_percent'])
        leverage = int(config['trading']['leverage'])
        
        # 获取当前价格
        current_price = float(order_manager.get_current_price())
        
        # 计算开仓数量 (USDT金额 * 杠杆 * 百分比 / 当前价格)
        amount = trade_status['balance'] * leverage * (position_percent / 100) / current_price
        # 四舍五入到合适的精度
        amount = round(amount, 3)
        
        # 市价开仓
        order = order_manager.client.market_order(side, amount)
        
        # 记录交易
        order_manager.record_trade(order, current_price, amount, 'FILLED')
        
        # 更新持仓状态
        trade_status['position'] = side
        order_manager.update_position(side)
        
        # 创建止盈止损订单
        stop_profit_percent = float(config['trading']['stop_profit'])
        stop_loss_percent = float(config['trading']['stop_loss'])
        
        # 计算止盈止损价格
        if side == 'BUY':
            stop_profit_price = current_price * (1 + stop_profit_percent / 100)
            stop_loss_price = current_price * (1 - stop_loss_percent / 100)
            stop_profit_side = 'SELL'
            stop_loss_side = 'SELL'
        else:  # SELL
            stop_profit_price = current_price * (1 - stop_profit_percent / 100)
            stop_loss_price = current_price * (1 + stop_loss_percent / 100)
            stop_profit_side = 'BUY'
            stop_loss_side = 'BUY'
        
        # 创建止盈订单
        stop_profit_order = order_manager.client.stop_order(
            stop_profit_side, stop_profit_price, True
        )
        order_manager.record_trade(stop_profit_order, None, None, 'NEW')
        
        # 创建止损订单
        stop_loss_order = order_manager.client.stop_order(
            stop_loss_side, stop_loss_price, True
        )
        order_manager.record_trade(stop_loss_order, None, None, 'NEW')
        
        # 启动持仓定时器
        order_manager.start_position_timer(lambda: close_position_callback(side))
        
        return jsonify({'status': 'success', 'message': f'{side}开仓成功'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'开仓失败: {str(e)}'})

# 平仓回调函数
def close_position_callback(position_side):
    if not position_side:
        return
    
    try:
        # 市价平仓
        close_side = 'BUY' if position_side == 'SELL' else 'SELL'
        order = order_manager.client.market_order(close_side, True)
        
        # 更新状态
        trade_status['position'] = None
        order_manager.update_position(None)
        
        # 记录交易
        current_price = order_manager.get_current_price()
        order_manager.record_trade(order, current_price, order.get('executedQty'), 'FILLED')
        
        print(f"自动平仓成功: {order.get('orderId')}")
    except Exception as e:
        print(f"自动平仓失败: {str(e)}")


@app.route('/api/trades')
def get_trades():
    # 获取最近交易记录
    trades = order_manager.get_recent_trades()
    return jsonify(trades)

@app.route('/api/restore')
def restore_status():
    # 从OrderManager加载之前的状态
    status = order_manager.restore_status()
    
    # 更新全局交易状态
    trade_status['position'] = status['position']
    trade_status['disabled'] = status['disabled']
    if status['disabled']:
        trade_status['disabled_until'] = status['disabled_until']
    trade_status['consecutive_losses'] = status['consecutive_losses']
    
    # 返回当前持仓状态和余额
    return jsonify({
        'position': trade_status['position'],
        'balance': trade_status['balance'],
        'disabled': trade_status['disabled'],
        'disabled_until': status.get('disabled_until'),
        'consecutive_losses': status.get('consecutive_losses')
    })

@app.route('/config')
def config_page():
    # 渲染配置页面
    return render_template('config.html')

@app.route('/api/get_config')
def get_config():
    # 从config.ini读取当前配置
    config_data = {}
    for section in config.sections():
        config_data[section] = {}
        for option in config.options(section):
            config_data[section][option] = config.get(section, option)
    return jsonify(config_data)

@app.route('/api/save_config', methods=['POST'])
def save_config():
    try:
        # 从请求中获取配置数据
        config_data = request.json
        print(f"Received config data: {config_data}")  # 添加日志
        
        # 确保配置数据是字典格式
        if not isinstance(config_data, dict):
            print("Invalid config format received")  # 添加日志
            return jsonify({'status': 'error', 'message': 'Invalid config format'}), 400
        
        # 更新配置文件
        if 'trading' not in config:
            config.add_section('trading')
        for option, value in config_data.items():
            config.set('trading', option, str(value))
            
        # 保存配置文件
        try:
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            print("Config file saved successfully")  # 添加日志
            return jsonify({'status': 'success'})
        except Exception as e:
            print(f"Error saving config file: {str(e)}")  # 添加日志
            return jsonify({'status': 'error', 'message': f'Failed to save config: {str(e)}'}), 500
            
    except Exception as e:
        print(f"Unexpected error in save_config: {str(e)}")  # 添加日志
        return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

@app.route('/api/price')
def get_price():
    # 获取实时价格
    price = order_manager.get_current_price()
    return jsonify({'price': price})

@app.route('/api/position')
def get_position():
    # 获取当前持仓状态
    return jsonify({
        'position': trade_status['position'],
        'balance': trade_status['balance']
    })

@app.route('/api/update_strategy', methods=['POST'])
def update_strategy():
    # 更新策略
    try:
        data = request.json
        strategy_name = data.get('strategy')
        
        if not strategy_name or strategy_name not in ['simple', 'ma', 'rsi', 'combined']:
            return jsonify({'status': 'error', 'message': '无效的策略名称'})
        
        # 创建新策略
        global strategy
        strategy = create_strategy(strategy_name)
        
        # 重新注册回调函数
        order_manager.client.register_kline_callback(lambda kline_data:
            # 如果有信号且自动交易开启，调用回调函数
            strategy_callback(strategy.analyze(kline_data))
        )
        
        print(f"策略已更新为: {strategy_name}")
        return jsonify({'status': 'success', 'message': f'策略已更新为: {strategy_name}'})
    except Exception as e:
        print(f"更新策略失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'更新策略失败: {str(e)}'})

@app.route('/api/auto_trading', methods=['POST'])
def auto_trading():
    # 更新自动交易状态
    try:
        data = request.json
        enabled = data.get('enabled', False)
        
        # 更新全局状态
        trade_status['auto_trading'] = enabled
        
        print(f"自动交易状态已更新: {'启用' if enabled else '禁用'}")
        return jsonify({'status': 'success', 'message': f"自动交易{'启用' if enabled else '禁用'}成功"})
    except Exception as e:
        print(f"更新自动交易状态失败: {str(e)}")
        return jsonify({'status': 'error', 'message': f'更新自动交易状态失败: {str(e)}'})

if __name__ == '__main__':
    # 服务启动时恢复交易状态
    status = order_manager.restore_status()
    trade_status['position'] = status['position']
    trade_status['disabled'] = status['disabled']
    if status['disabled']:
        trade_status['disabled_until'] = status['disabled_until']
    trade_status['consecutive_losses'] = status['consecutive_losses']
    
    # 初始化策略
    strategy = create_strategy()
    
    # 注册策略回调函数
    def strategy_callback(signal):
        """策略信号回调函数"""
        if signal and not trade_status['position'] and not trade_status['disabled']:
            print(f"收到策略信号: {signal}")
            try:
                # 自动执行交易
                if signal in ['BUY', 'SELL']:
                    # 计算开仓数量
                    symbol = config['trading']['symbol']
                    position_percent = float(config['trading']['position_percent'])
                    leverage = int(config['trading']['leverage'])
                    
                    # 获取当前价格
                    current_price = float(order_manager.get_current_price())
                    
                    # 计算开仓数量
                    amount = trade_status['balance'] * leverage * (position_percent / 100) / current_price
                    amount = round(amount, 3)
                    
                    # 市价开仓
                    order = order_manager.client.market_order(signal, amount)
                    
                    # 记录交易
                    order_manager.record_trade(order, current_price, amount, 'FILLED')
                    
                    # 更新持仓状态
                    trade_status['position'] = signal
                    order_manager.update_position(signal)
                    
                    # 创建止盈止损订单
                    stop_profit_percent = float(config['trading']['stop_profit'])
                    stop_loss_percent = float(config['trading']['stop_loss'])
                    
                    # 计算止盈止损价格
                    if signal == 'BUY':
                        stop_profit_price = current_price * (1 + stop_profit_percent / 100)
                        stop_loss_price = current_price * (1 - stop_loss_percent / 100)
                        stop_profit_side = 'SELL'
                        stop_loss_side = 'SELL'
                    else:  # SELL
                        stop_profit_price = current_price * (1 - stop_profit_percent / 100)
                        stop_loss_price = current_price * (1 + stop_loss_percent / 100)
                        stop_profit_side = 'BUY'
                        stop_loss_side = 'BUY'
                    
                    # 创建止盈订单
                    stop_profit_order = order_manager.client.stop_order(
                        stop_profit_side, stop_profit_price, True
                    )
                    order_manager.record_trade(stop_profit_order, None, None, 'NEW')
                    
                    # 创建止损订单
                    stop_loss_order = order_manager.client.stop_order(
                        stop_loss_side, stop_loss_price, True
                    )
                    order_manager.record_trade(stop_loss_order, None, None, 'NEW')
                    
                    # 启动持仓定时器
                    order_manager.start_position_timer(lambda: close_position_callback(signal))
                    
                    print(f"策略自动开仓成功: {signal}")
            except Exception as e:
                print(f"策略自动开仓失败: {str(e)}")
    
    # 将回调函数注册到BinanceClient
    order_manager.client.register_kline_callback(lambda kline_data: 
        # 分析K线数据并生成信号
        strategy_callback(strategy.analyze(kline_data))
    )
    
    print(f"服务启动成功，当前状态: 持仓={trade_status['position']}, 禁用={trade_status['disabled']}")
    app.run(debug=True, port=5000, host='127.0.0.1')