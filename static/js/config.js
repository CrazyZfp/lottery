document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('config-form');
    
    // 页面加载时获取当前配置
    fetch('/api/get_config')
       .then(response => response.json())
       .then(data => {
            const tradingConfig = data.trading;
            form.elements['symbol'].value = tradingConfig.symbol;
            form.elements['leverage'].value = tradingConfig.leverage;
            form.elements['position_percent'].value = tradingConfig.position_percent;
            form.elements['initial_balance'].value = tradingConfig.initial_balance;
            form.elements['max_hold_time'].value = tradingConfig.max_hold_time;
            form.elements['stop_profit'].value = tradingConfig.stop_profit;
            form.elements['stop_loss'].value = tradingConfig.stop_loss;
            form.elements['consecutive_losses'].value = tradingConfig.consecutive_losses;
            form.elements['disable_time'].value = tradingConfig.disable_time;
        })
       .catch(error => console.error('Error fetching config:', error));

    // 表单提交事件处理
    form.addEventListener('submit', (event) => {
        event.preventDefault();
        const formData = new FormData(event.target);
        const configData = {
            symbol: formData.get('symbol'),
            leverage: formData.get('leverage'),
            position_percent: formData.get('position_percent'),
            initial_balance: formData.get('initial_balance'),
            max_hold_time: formData.get('max_hold_time'),
            stop_profit: formData.get('stop_profit'),
            stop_loss: formData.get('stop_loss'),
            consecutive_losses: formData.get('consecutive_losses'),
            disable_time: formData.get('disable_time')
        };

        fetch('/api/save_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        })
       .then(response => response.json())
       .then(data => {
            if (data.status === 'success') {
                alert('配置保存成功，请返回主页查看更新后的配置');
                // 添加一个返回主页的链接
                const messageDiv = document.createElement('div');
                messageDiv.className = 'success-message';
                messageDiv.innerHTML = '配置已更新，<a href="/">点击返回主页</a>查看最新配置';
                form.appendChild(messageDiv);
            } else {
                alert(`配置保存失败: ${data.message || '未知错误'}`);
            }
        })
       .catch(error => {
            console.error('Error saving config:', error);
            alert('配置保存失败: 网络错误');
        });
    });
});