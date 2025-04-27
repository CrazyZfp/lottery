/**
 * Puppeteer自动化测试脚本
 * 用于测试页面的动画效果和响应式设计
 */

const puppeteer = require('puppeteer');

(async () => {
  // 启动浏览器
  const browser = await puppeteer.launch({
    headless: false, // 设置为false以便观察测试过程
    defaultViewport: null, // 使用默认视口
    args: ['--start-maximized'] // 最大化窗口
  });

  try {
    // 创建新页面
    const page = await browser.newPage();
    console.log('开始测试页面...');

    // 访问页面
    await page.goto('http://localhost:8000/templates/index.html', {
      waitUntil: 'networkidle2'
    });
    console.log('页面加载完成');

    // 等待页面加载动画完成
    await page.waitForTimeout(2000);

    // 测试页面元素是否正确加载
    const appIcon = await page.$('.app-icon');
    const title = await page.$('h1');
    const infoPanel = await page.$('.info-panel');
    const actionButtons = await page.$('.action-buttons');

    if (appIcon && title && infoPanel && actionButtons) {
      console.log('✓ 页面元素正确加载');
    } else {
      console.error('✗ 页面元素加载失败');
    }

    // 测试按钮悬停效果
    console.log('测试按钮悬停效果...');
    await page.hover('#long-btn');
    await page.waitForTimeout(500);

    // 测试按钮点击效果
    console.log('测试按钮点击效果...');
    await page.mouse.down();
    await page.waitForTimeout(300);
    await page.mouse.up();
    await page.waitForTimeout(500);

    // 测试价格变化动画
    console.log('测试价格变化动画...');
    await page.evaluate(() => {
      const priceElement = document.getElementById('price');
      const priceChangeElement = document.getElementById('price-change');
      
      if (priceElement && priceChangeElement) {
        priceElement.textContent = '45000';
        priceChangeElement.textContent = '+2.5%';
        priceChangeElement.className = 'price-change up';
      }
    });
    await page.waitForTimeout(1000);

    // 测试响应式设计 - 桌面视图
    console.log('测试桌面视图响应式设计...');
    await page.setViewport({ width: 1200, height: 800 });
    await page.waitForTimeout(1000);

    const isDesktop = await page.evaluate(() => {
      return document.body.classList.contains('desktop-device');
    });

    if (isDesktop) {
      console.log('✓ 正确识别为桌面设备');
    } else {
      console.error('✗ 未正确识别为桌面设备');
    }

    // 截图桌面视图
    await page.screenshot({ path: './desktop-view.png' });
    console.log('已保存桌面视图截图');

    // 测试响应式设计 - 移动视图
    console.log('测试移动视图响应式设计...');
    await page.setViewport({ width: 375, height: 667 }); // iPhone 8 尺寸
    await page.waitForTimeout(1000);

    const isMobile = await page.evaluate(() => {
      return document.body.classList.contains('mobile-device');
    });

    if (isMobile) {
      console.log('✓ 正确识别为移动设备');
    } else {
      console.error('✗ 未正确识别为移动设备');
    }

    // 检查移动视图下的布局
    const isMobileLayout = await page.evaluate(() => {
      const configLink = document.querySelector('.config-link');
      const style = window.getComputedStyle(configLink);
      return style.flexDirection === 'column';
    });

    if (isMobileLayout) {
      console.log('✓ 移动视图布局正确');
    } else {
      console.error('✗ 移动视图布局不正确');
    }

    // 截图移动视图
    await page.screenshot({ path: './mobile-view.png' });
    console.log('已保存移动视图截图');

    console.log('测试完成!');

  } catch (error) {
    console.error('测试过程中发生错误:', error);
  } finally {
    // 等待一段时间后关闭浏览器
    await new Promise(resolve => setTimeout(resolve, 5000));
    await browser.close();
  }
})();