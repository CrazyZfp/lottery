document.addEventListener('DOMContentLoaded', function() {
    const buyBtn = document.getElementById('buy-btn');
    const sellBtn = document.getElementById('sell-btn');
    const closeBtn = document.getElementById('close-btn');
    const autoBtn = document.getElementById('auto-btn');
    const strategySelect = document.getElementById('strategy-select');
    const statusDiv = document.getElementById('status-message');
    const priceChangeSpan = document.getElementById('price-change');
    
    // 自动交易状态
    let autoTrading = false;
    
    // 交易状态
    let tradeStatus = {
        disabled: false,
        disabled_until: null,
        position: null,
        lastPrice: null,
        currentPrice: null
    };
    
    // 获取实时价格
    function updatePrice() {
        fetch('/api/price')
            .then(response => response.json())
            .then(data => {
                if (data.price) {
                    // 保存上一次价格
                    tradeStatus.lastPrice = tradeStatus.currentPrice;
                    tradeStatus.currentPrice = parseFloat(data.price);
                    
                    // 更新价格显示
                    document.getElementById('price').textContent = data.price;
                    
                    // 显示价格变动
                    if (tradeStatus.lastPrice !== null) {
                        const priceChange = tradeStatus.currentPrice - tradeStatus.lastPrice;
                        const changePercent = (priceChange / tradeStatus.lastPrice * 100).toFixed(2);
                        
                        if (priceChange > 0) {
                            priceChangeSpan.textContent = `+${changePercent}%`;
                            priceChangeSpan.className = 'price-change up';
                        } else if (priceChange < 0) {
                            priceChangeSpan.textContent = `${changePercent}%`;
                            priceChangeSpan.className = 'price-change down';
                        } else {
                            priceChangeSpan.textContent = '0.00%';
                            priceChangeSpan.className = 'price-change';
                        }
                    }
                }
            })
            .catch(error => {
                console.error('获取价格失败:', error);
                showStatus('获取价格失败，请检查网络连接', 'error');
            });
    }
    
    // 更新持仓状态
    function updatePosition() {
        fetch('/api/position')
            .then(response => response.json())
            .then(data => {
                document.getElementById('position').textContent = 
                    data.position || '无';
                document.getElementById('balance').textContent = data.balance;
                
                // 更新交易状态
                tradeStatus.position = data.position;
                tradeStatus.disabled = data.disabled;
                tradeStatus.disabled_until = data.disabled_until;
                
                // 更新按钮状态
                updateButtonStatus();
            })
            .catch(error => {
                console.error('获取持仓状态失败:', error);
            });
    }
    
    // 更新按钮状态
    function updateButtonStatus() {
        // 如果禁用状态，显示倒计时
        if (tradeStatus.disabled && tradeStatus.disabled_until) {
            const remainingTime = Math.max(0, Math.floor((tradeStatus.disabled_until - Date.now()/1000)));
            statusDiv.textContent = `交易功能已禁用，剩余时间: ${remainingTime}秒`;
            statusDiv.style.display = 'block';
            statusDiv.className = 'status-message error';
            
            // 禁用所有按钮
            buyBtn.disabled = true;
            sellBtn.disabled = true;
            closeBtn.disabled = true;
        } else {
            statusDiv.style.display = 'none';
            
            // 根据持仓状态启用/禁用按钮
            if (tradeStatus.position) {
                // 有持仓时，禁用开仓按钮，启用平仓按钮
                buyBtn.disabled = true;
                sellBtn.disabled = true;
                closeBtn.disabled = false;
            } else {
                // 无持仓时，启用开仓按钮，禁用平仓按钮
                buyBtn.disabled = false;
                sellBtn.disabled = false;
                closeBtn.disabled = true;
            }
        }
    }
    
    // 快捷下单
    function quickOrder(side) {
        // 显示加载状态
        statusDiv.textContent = '处理中...';
        statusDiv.style.display = 'block';
        statusDiv.className = 'status-message';
        
        // 禁用按钮防止重复点击
        buyBtn.disabled = true;
        sellBtn.disabled = true;
        closeBtn.disabled = true;
        
        fetch('/api/quick_order', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ side: side })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                // 成功消息
                statusDiv.textContent = data.message || '操作成功';
                statusDiv.className = 'status-message success';
                // 更新状态
                updatePosition();
            } else {
                // 错误消息
                statusDiv.textContent = data.message || '操作失败';
                statusDiv.className = 'status-message error';
                // 恢复按钮状态
                updateButtonStatus();
            }
            
            // 3秒后隐藏消息
            setTimeout(() => {
                if (statusDiv.className.includes('success') || statusDiv.className.includes('error')) {
                    statusDiv.style.display = 'none';
                }
            }, 3000);
        })
        .catch(error => {
            console.error('请求失败:', error);
            statusDiv.textContent = '网络错误，请重试';
            statusDiv.className = 'status-message error';
            // 恢复按钮状态
            updateButtonStatus();
        });
    }
    
    // 显示状态消息
    function showStatus(message, type = '') {
        statusDiv.textContent = message;
        statusDiv.style.display = 'block';
        
        if (type === 'success') {
            statusDiv.className = 'status-message success';
        } else if (type === 'error') {
            statusDiv.className = 'status-message error';
        } else {
            statusDiv.className = 'status-message';
        }
        
        // 如果是成功或错误消息，3秒后自动隐藏
        if (type === 'success' || type === 'error') {
            setTimeout(() => {
                statusDiv.style.display = 'none';
            }, 3000);
        }
    }
    
    // 更新策略
    function updateStrategy() {
        const strategy = strategySelect.value;
        fetch('/api/update_strategy', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ strategy: strategy })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                document.getElementById('current-strategy').textContent = strategySelect.options[strategySelect.selectedIndex].text;
                showStatus(`策略已更新为: ${strategySelect.options[strategySelect.selectedIndex].text}`, 'success');
            } else {
                showStatus(data.message || '更新策略失败', 'error');
            }
        })
        .catch(error => {
            console.error('更新策略失败:', error);
            showStatus('更新策略失败，请检查网络连接', 'error');
        });
    }
    
    // 切换自动交易状态
    function toggleAutoTrading() {
        autoTrading = !autoTrading;
        
        if (autoTrading) {
            autoBtn.textContent = '停止自动';
            autoBtn.classList.add('active');
            showStatus('自动交易已启动，系统将根据策略信号自动开仓', 'success');
        } else {
            autoBtn.textContent = '自动交易';
            autoBtn.classList.remove('active');
            showStatus('自动交易已停止', 'success');
        }
        
        // 发送到服务器更新自动交易状态
        fetch('/api/auto_trading', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ enabled: autoTrading })
        })
        .catch(error => {
            console.error('更新自动交易状态失败:', error);
        });
    }
    
    // 按钮事件绑定
    buyBtn.addEventListener('click', () => quickOrder('BUY'));
    sellBtn.addEventListener('click', () => quickOrder('SELL'));
    closeBtn.addEventListener('click', () => quickOrder('CLOSE'));
    autoBtn.addEventListener('click', toggleAutoTrading);
    strategySelect.addEventListener('change', updateStrategy);
    
    // 初始化 - 恢复状态
    fetch('/api/restore')
        .then(response => response.json())
        .then(data => {
            tradeStatus.position = data.position;
            tradeStatus.disabled = data.disabled;
            tradeStatus.disabled_until = data.disabled_until;
            
            document.getElementById('position').textContent = data.position || '无';
            document.getElementById('balance').textContent = data.balance;
            
            updateButtonStatus();
            updatePrice();
        })
        .catch(error => {
            console.error('恢复状态失败:', error);
        });
    
    // 定时刷新
    setInterval(updatePrice, 3000);
    setInterval(updatePosition, 10000);
    
    // 定时更新禁用状态倒计时
    setInterval(() => {
        if (tradeStatus.disabled && tradeStatus.disabled_until) {
            const remainingTime = Math.max(0, Math.floor((tradeStatus.disabled_until - Date.now()/1000)));
            if (remainingTime > 0) {
                statusDiv.textContent = `交易功能已禁用，剩余时间: ${remainingTime}秒`;
            } else {
                // 禁用时间已过，刷新状态
                updatePosition();
            }
        }
    }, 1000);
});