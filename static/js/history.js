document.addEventListener('DOMContentLoaded', function() {
    const tableBody = document.querySelector('#trade-history tbody');
    
    // 加载交易记录
    function loadTradeHistory() {
        // 显示加载状态
        tableBody.innerHTML = '<tr><td colspan="6" class="loading">加载中...</td></tr>';
        
        fetch('/api/trades')
            .then(response => response.json())
            .then(data => {
                tableBody.innerHTML = '';
                
                if (!data || data.length === 0) {
                    tableBody.innerHTML = '<tr><td colspan="6" class="no-data">暂无交易记录</td></tr>';
                    return;
                }
                
                data.forEach(trade => {
                    const row = document.createElement('tr');
                    
                    // 格式化时间
                    let formattedTime = trade.timestamp;
                    try {
                        formattedTime = new Date(trade.timestamp).toLocaleString();
                    } catch (e) {
                        console.error('时间格式化错误:', e);
                    }
                    
                    // 格式化盈亏显示
                    let pnlClass = '';
                    let pnlValue = trade.pnl || '-';
                    if (pnlValue !== '-') {
                        pnlValue = parseFloat(pnlValue);
                        if (pnlValue > 0) {
                            pnlClass = 'profit';
                            pnlValue = '+' + pnlValue.toFixed(2);
                        } else if (pnlValue < 0) {
                            pnlClass = 'loss';
                            pnlValue = pnlValue.toFixed(2);
                        } else {
                            pnlValue = '0.00';
                        }
                    }
                    
                    // 格式化状态
                    let statusText = trade.status;
                    switch (trade.status) {
                        case 'FILLED': statusText = '已成交'; break;
                        case 'NEW': statusText = '新建'; break;
                        case 'PARTIALLY_FILLED': statusText = '部分成交'; break;
                        case 'CANCELED': statusText = '已取消'; break;
                        case 'EXPIRED': statusText = '已过期'; break;
                    }
                    
                    row.innerHTML = `
                        <td>${formattedTime}</td>
                        <td class="${trade.side === 'BUY' ? 'buy-side' : 'sell-side'}">${trade.side === 'BUY' ? '买多' : '卖空'}</td>
                        <td>${trade.exec_price || trade.order_price || '-'}</td>
                        <td>${trade.exec_qty || trade.order_qty || '-'}</td>
                        <td>${statusText}</td>
                        <td class="${pnlClass}">${pnlValue}</td>
                    `;
                    
                    tableBody.appendChild(row);
                });
            })
            .catch(error => {
                console.error('获取交易记录失败:', error);
                tableBody.innerHTML = '<tr><td colspan="6" class="error">获取交易记录失败，请刷新重试</td></tr>';
            });
    }
    
    // 添加刷新按钮
    const refreshBtn = document.createElement('button');
    refreshBtn.textContent = '刷新';
    refreshBtn.className = 'btn refresh-btn';
    refreshBtn.addEventListener('click', loadTradeHistory);
    document.querySelector('.back-link').prepend(refreshBtn);
    
    // 初始化加载
    loadTradeHistory();
    
    // 定时刷新
    setInterval(loadTradeHistory, 30000);
});