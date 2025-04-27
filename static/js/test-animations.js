/**
 * 动画和响应式设计测试脚本
 * 用于验证页面在不同设备和屏幕尺寸下的表现
 */

document.addEventListener('DOMContentLoaded', () => {
    console.log('开始测试动画和响应式设计...');
    
    // 测试页面加载动画
    testPageLoadAnimation();
    
    // 测试按钮动画效果
    testButtonAnimations();
    
    // 测试价格变化动画
    testPriceChangeAnimation();
    
    // 测试响应式布局
    testResponsiveLayout();
    
    // 测试设备适配
    testDeviceAdaptation();
    
    console.log('所有测试完成!');
});

/**
 * 测试页面加载动画
 */
function testPageLoadAnimation() {
    console.log('测试页面加载动画...');
    
    // 检查页面加载器是否存在
    const pageLoader = document.querySelector('.page-loader');
    if (!pageLoader) {
        console.error('页面加载器元素不存在!');
        return;
    }
    
    // 检查页面加载动画是否正确隐藏
    setTimeout(() => {
        if (pageLoader.classList.contains('hidden') && pageLoader.style.display === 'none') {
            console.log('✓ 页面加载动画正确隐藏');
        } else {
            console.error('✗ 页面加载动画未正确隐藏');
        }
    }, 2000);
    
    // 检查容器元素是否正确显示
    const container = document.querySelector('.container');
    setTimeout(() => {
        if (parseFloat(getComputedStyle(container).opacity) === 1) {
            console.log('✓ 容器元素正确显示');
        } else {
            console.error('✗ 容器元素未正确显示');
        }
    }, 1500);
}

/**
 * 测试按钮动画效果
 */
function testButtonAnimations() {
    console.log('测试按钮动画效果...');
    
    const buttons = document.querySelectorAll('.btn');
    if (buttons.length === 0) {
        console.error('未找到按钮元素!');
        return;
    }
    
    // 模拟鼠标悬停和点击事件
    setTimeout(() => {
        // 测试第一个按钮
        const testButton = buttons[0];
        
        // 模拟鼠标悬停
        const mouseenterEvent = new Event('mouseenter');
        testButton.dispatchEvent(mouseenterEvent);
        
        setTimeout(() => {
            // 检查悬停效果
            const transform = getComputedStyle(testButton).transform;
            const hasTransform = transform !== 'none' && transform !== 'matrix(1, 0, 0, 1, 0, 0)';
            
            if (hasTransform) {
                console.log('✓ 按钮悬停效果正常');
            } else {
                console.error('✗ 按钮悬停效果异常');
            }
            
            // 模拟鼠标离开
            const mouseleaveEvent = new Event('mouseleave');
            testButton.dispatchEvent(mouseleaveEvent);
        }, 300);
    }, 2500);
}

/**
 * 测试价格变化动画
 */
function testPriceChangeAnimation() {
    console.log('测试价格变化动画...');
    
    const priceElement = document.getElementById('price');
    const priceChangeElement = document.getElementById('price-change');
    
    if (!priceElement || !priceChangeElement) {
        console.error('价格元素不存在!');
        return;
    }
    
    // 模拟价格变化
    setTimeout(() => {
        // 更新价格
        priceElement.textContent = '45000';
        
        // 添加价格变化类
        priceChangeElement.textContent = '+2.5%';
        priceChangeElement.className = 'price-change up';
        
        // 检查动画类是否被添加
        setTimeout(() => {
            if (priceChangeElement.classList.contains('bounce-animation')) {
                console.log('✓ 价格变化动画正常');
            } else {
                console.warn('! 价格变化动画可能未触发 (这可能是因为MutationObserver未检测到类变化)');
            }
        }, 100);
    }, 3000);
}

/**
 * 测试响应式布局
 */
function testResponsiveLayout() {
    console.log('测试响应式布局...');
    
    // 获取当前窗口宽度
    const windowWidth = window.innerWidth;
    console.log(`当前窗口宽度: ${windowWidth}px`);
    
    // 检查是否应用了正确的响应式样式
    if (windowWidth <= 768) {
        // 移动设备布局
        const actionButtons = document.querySelector('.action-buttons');
        const computedStyle = getComputedStyle(actionButtons);
        const gridTemplateColumns = computedStyle.gridTemplateColumns;
        
        // 检查按钮布局是否为两列
        if (gridTemplateColumns.split(' ').length === 2) {
            console.log('✓ 移动设备按钮布局正确 (两列)');
        } else {
            console.error('✗ 移动设备按钮布局不正确');
        }
        
        // 检查配置链接是否垂直排列
        const configLink = document.querySelector('.config-link');
        const configLinkStyle = getComputedStyle(configLink);
        
        if (configLinkStyle.flexDirection === 'column') {
            console.log('✓ 移动设备配置链接布局正确 (垂直排列)');
        } else {
            console.error('✗ 移动设备配置链接布局不正确');
        }
    } else {
        // 桌面设备布局
        const actionButtons = document.querySelector('.action-buttons');
        const computedStyle = getComputedStyle(actionButtons);
        
        // 检查配置链接是否水平排列
        const configLink = document.querySelector('.config-link');
        const configLinkStyle = getComputedStyle(configLink);
        
        if (configLinkStyle.flexDirection !== 'column') {
            console.log('✓ 桌面设备配置链接布局正确 (水平排列)');
        } else {
            console.error('✗ 桌面设备配置链接布局不正确');
        }
    }
}

/**
 * 测试设备适配
 */
function testDeviceAdaptation() {
    console.log('测试设备适配...');
    
    // 检查是否正确添加了设备类
    const isMobile = window.innerWidth < 768;
    const bodyClasses = document.body.classList;
    
    if (isMobile && bodyClasses.contains('mobile-device')) {
        console.log('✓ 正确识别为移动设备');
    } else if (!isMobile && bodyClasses.contains('desktop-device')) {
        console.log('✓ 正确识别为桌面设备');
    } else {
        console.error('✗ 设备类型识别错误');
    }
    
    // 测试窗口大小变化响应
    console.log('测试窗口大小变化响应...');
    console.log('请手动调整浏览器窗口大小，然后检查控制台输出');
    
    // 添加窗口大小变化监听器用于测试
    window.addEventListener('resize', () => {
        const currentWidth = window.innerWidth;
        const isMobileNow = currentWidth < 768;
        
        console.log(`窗口大小变化: ${currentWidth}px, ${isMobileNow ? '移动设备' : '桌面设备'}`);
        
        // 检查设备类是否正确更新
        setTimeout(() => {
            if (isMobileNow && document.body.classList.contains('mobile-device')) {
                console.log('✓ 窗口大小变化后正确更新为移动设备类');
            } else if (!isMobileNow && document.body.classList.contains('desktop-device')) {
                console.log('✓ 窗口大小变化后正确更新为桌面设备类');
            } else {
                console.error('✗ 窗口大小变化后设备类未正确更新');
            }
        }, 300);
    });
}