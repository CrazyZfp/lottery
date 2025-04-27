/**
 * 交互动画效果脚本
 * 为彩票应用添加现代化的动画和交互效果
 */

document.addEventListener('DOMContentLoaded', () => {
    // 隐藏页面加载动画
    hidePageLoader();
    
    // 页面加载动画
    animatePageLoad();
    
    // 为按钮添加悬停和点击效果
    setupButtonAnimations();
    
    // 为价格变化添加动画效果
    setupPriceChangeAnimations();
    
    // 为信息面板添加动画效果
    setupInfoPanelAnimations();
    
    // 检测设备类型并适配
    detectDeviceAndAdapt();
});

/**
 * 隐藏页面加载动画
 */
function hidePageLoader() {
    const pageLoader = document.querySelector('.page-loader');
    if (pageLoader) {
        setTimeout(() => {
            pageLoader.classList.add('hidden');
            setTimeout(() => {
                pageLoader.style.display = 'none';
            }, 500);
        }, 800);
    }
}

/**
 * 页面加载动画
 */
function animatePageLoad() {
    const container = document.querySelector('.container');
    const elements = container.querySelectorAll('h1, .info-panel, .action-buttons, .config-link');
    
    // 初始状态设置
    container.style.opacity = '0';
    container.style.transform = 'translateY(20px)';
    
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
    });
    
    // 容器动画
    setTimeout(() => {
        container.style.opacity = '1';
        container.style.transform = 'translateY(0)';
    }, 100);
    
    // 元素依次动画
    elements.forEach((el, index) => {
        setTimeout(() => {
            el.style.opacity = '1';
            el.style.transform = 'translateY(0)';
        }, 300 + (index * 150));
    });
}

/**
 * 为按钮添加悬停和点击效果
 */
function setupButtonAnimations() {
    const buttons = document.querySelectorAll('.btn');
    
    buttons.forEach(btn => {
        // 悬停效果
        btn.addEventListener('mouseenter', () => {
            btn.style.transform = 'translateY(-3px)';
            btn.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.15)';
        });
        
        btn.addEventListener('mouseleave', () => {
            btn.style.transform = 'translateY(0)';
            btn.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
        });
        
        // 点击效果
        btn.addEventListener('mousedown', () => {
            btn.style.transform = 'translateY(1px)';
            btn.style.boxShadow = '0 2px 4px rgba(0, 0, 0, 0.1)';
        });
        
        btn.addEventListener('mouseup', () => {
            btn.style.transform = 'translateY(-3px)';
            btn.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.15)';
        });
    });
}

/**
 * 为价格变化添加动画效果
 */
function setupPriceChangeAnimations() {
    // 模拟价格变化监听
    const priceElement = document.getElementById('price');
    const priceChangeElement = document.getElementById('price-change');
    
    // 当价格更新时添加闪烁效果
    if (window.MutationObserver) {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList' || mutation.type === 'characterData') {
                    flashElement(priceElement);
                }
            });
        });
        
        observer.observe(priceElement, { childList: true, characterData: true, subtree: true });
    }
    
    // 当价格变化状态更新时添加动画
    if (priceChangeElement) {
        if (window.MutationObserver) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                        animatePriceChange(priceChangeElement);
                    }
                });
            });
            
            observer.observe(priceChangeElement, { attributes: true });
        }
    }
}

/**
 * 为信息面板添加动画效果
 */
function setupInfoPanelAnimations() {
    const infoPanel = document.querySelector('.info-panel');
    const infoPanelItems = infoPanel.querySelectorAll('div');
    
    infoPanelItems.forEach(item => {
        // 在移动设备上使用触摸事件，在桌面设备上使用鼠标事件
        if ('ontouchstart' in window) {
            item.addEventListener('touchstart', () => {
                item.style.backgroundColor = 'rgba(249, 249, 249, 0.95)';
                item.style.transform = 'translateX(5px)';
            });
            
            item.addEventListener('touchend', () => {
                item.style.backgroundColor = 'transparent';
                item.style.transform = 'translateX(0)';
            });
        } else {
            item.addEventListener('mouseenter', () => {
                item.style.backgroundColor = 'rgba(249, 249, 249, 0.95)';
                item.style.transform = 'translateX(5px)';
            });
            
            item.addEventListener('mouseleave', () => {
                item.style.backgroundColor = 'transparent';
                item.style.transform = 'translateX(0)';
            });
        }
    });
}

/**
 * 元素闪烁效果
 * @param {HTMLElement} element - 需要闪烁的元素
 */
function flashElement(element) {
    element.classList.add('flash-animation');
    setTimeout(() => {
        element.classList.remove('flash-animation');
    }, 1000);
}

/**
 * 价格变化动画
 * @param {HTMLElement} element - 价格变化元素
 */
function animatePriceChange(element) {
    element.classList.add('bounce-animation');
    setTimeout(() => {
        element.classList.remove('bounce-animation');
    }, 1000);
}

/**
 * 检测设备类型并适配
 */
function detectDeviceAndAdapt() {
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth < 768;
    const container = document.querySelector('.container');
    const buttons = document.querySelectorAll('.btn');
    
    if (isMobile) {
        // 移动设备适配
        document.body.classList.add('mobile-device');
        
        // 调整按钮大小，使其更容易点击
        buttons.forEach(btn => {
            btn.style.padding = '12px 20px';
            btn.style.fontSize = '1rem';
        });
        
        // 为移动设备添加触摸反馈
        document.querySelectorAll('button, a, select').forEach(el => {
            el.addEventListener('touchstart', function() {
                this.style.opacity = '0.7';
            });
            
            el.addEventListener('touchend', function() {
                this.style.opacity = '1';
            });
        });
    } else {
        // 桌面设备适配
        document.body.classList.add('desktop-device');
    }
    
    // 监听窗口大小变化，动态调整布局
    window.addEventListener('resize', () => {
        if (window.innerWidth < 768 && !document.body.classList.contains('mobile-device')) {
            document.body.classList.remove('desktop-device');
            document.body.classList.add('mobile-device');
        } else if (window.innerWidth >= 768 && !document.body.classList.contains('desktop-device')) {
            document.body.classList.remove('mobile-device');
            document.body.classList.add('desktop-device');
        }
    });
}