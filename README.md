# Lottery 量化交易管理系统

## 项目简介
本项目是一个基于 Python 的量化交易管理系统，主要用于自动化管理加密货币交易订单，支持交易记录、风控管理、策略执行等功能。系统集成了币安 API，适合个人或团队进行数字货币量化交易。

## 目录结构
- `main.py`：程序入口，负责启动服务。
- `order_manager.py`：订单管理核心模块，负责订单记录、风控、持仓管理等。
- `strategy.py`：交易策略实现。
- `binance_client.py`：币安 API 封装。
- `config.ini`：系统配置文件。
- `requirements.txt`：依赖包列表。
- `static/`：静态资源（CSS/JS）。
- `templates/`：前端页面模板。
- `trades.csv`：交易记录文件。

## 安装依赖
建议使用 Python 3.8 及以上版本。

```bash
pip install -r requirements.txt
```

## 配置说明
请根据实际需求修改 `config.ini`，配置交易参数、API 密钥等。

## 运行方式
```bash
python main.py
```

## 主要功能
- 自动记录每笔交易到 CSV 文件
- 支持连续亏损风控，自动禁用交易
- 交易日志与错误日志记录
- 可扩展的策略模块
- 前端页面展示交易历史与配置

## 注意事项
- 请确保 `config.ini` 配置正确，API 密钥安全保管
- 交易涉及资金风险，请谨慎使用

## License
MIT