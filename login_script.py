import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta
import aiofiles
import random
import requests
import os
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 从环境变量中获取 Telegram Bot Token 和 Chat ID
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# 全局浏览器实例
browser = None
message = ""

async def init_browser():
    """初始化浏览器实例，添加反检测措施"""
    global browser
    if not browser:
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080'
            ],
            ignoreHTTPSErrors=True,
            autoClose=False
        )
    return browser

async def login(username, password, panel):
    """登录函数"""
    global browser
    page = None
    serviceName = 'CT8' if 'ct8' in panel.lower() else 'Serv00'
    
    try:
        # 初始化浏览器
        browser = await init_browser()
        page = await browser.newPage()
        
        # 设置反检测
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        await page.evaluateOnNewDocument('''() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        }''')
        
        await page.setViewport({'width': 1920, 'height': 1080})
        
        # 修复请求拦截 - 移除有问题的部分
        # 不再拦截请求，避免资源加载问题
        
        url = f'https://{panel}/login/?next=/'
        logger.info(f'正在访问: {url} - 账号: {username}')
        
        # 导航到登录页面
        try:
            await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})
        except Exception as e:
            logger.warning(f'页面加载可能不完全: {e}')
        
        # 等待关键元素加载
        try:
            await page.waitForSelector('#id_username', {'timeout': 15000})
            logger.info('找到用户名输入框')
        except Exception as e:
            logger.error(f'等待用户名输入框超时: {e}')
            return False

        # 输入用户名
        try:
            username_input = await page.querySelector('#id_username')
            if username_input:
                await username_input.click()
                await asyncio.sleep(0.3)
                
                # 清空输入框
                await page.evaluate('(input) => input.value = ""', username_input)
                
                # 输入用户名
                for char in username:
                    await username_input.type(char)
                    await asyncio.sleep(random.uniform(0.05, 0.1))
                
                logger.info('用户名输入完成')
        except Exception as e:
            logger.error(f'输入用户名时出错: {e}')
            return False

        # 输入密码
        try:
            password_input = await page.querySelector('#id_password')
            if password_input:
                await password_input.click()
                await asyncio.sleep(0.2)
                
                # 清空密码框
                await page.evaluate('(input) => input.value = ""', password_input)
                
                # 输入密码
                for char in password:
                    await password_input.type(char)
                    await asyncio.sleep(random.uniform(0.05, 0.1))
                
                logger.info('密码输入完成')
        except Exception as e:
            logger.error(f'输入密码时出错: {e}')
            return False

        # 查找登录按钮
        login_button = None
        button_selectors = [
            'button.button--primary[type="submit"]',
            'button[type="submit"].button--primary',
            '.login-form__button button',
            'button.button--primary',
            'button[type="submit"]'
        ]
        
        for selector in button_selectors:
            try:
                login_button = await page.querySelector(selector)
                if login_button:
                    logger.info(f'使用选择器找到按钮: {selector}')
                    break
            except:
                continue

        if not login_button:
            logger.error('无法找到登录按钮')
            return False

        # 点击按钮
        await login_button.click()
        logger.info('登录按钮点击完成')
        
        # 等待登录处理
        await asyncio.sleep(3)
        
        # 检查登录是否成功
        is_logged_in = await page.evaluate('''() => {
            // 检查登出链接
            const logoutBtn = document.querySelector('a[href*="/logout/"]');
            if (logoutBtn) return true;
            
            // 检查是否仍在登录页面
            const loginForm = document.querySelector('form[action*="/login/"]');
            if (loginForm) return false;
            
            // 检查页面内容
            const bodyText = document.body.innerText;
            if (bodyText.includes('Dashboard') || bodyText.includes('控制面板')) {
                return true;
            }
            
            return false;
        }''')
        
        logger.info(f'{serviceName}账号 {username} 登录{"成功" if is_logged_in else "失败"}')
        return is_logged_in
        
    except Exception as e:
        logger.error(f'{serviceName}账号 {username} 登录时出现错误: {str(e)}')
        return False
        
    finally:
        if page:
            await page.close()

async def shutdown_browser():
    """关闭浏览器实例"""
    global browser
    if browser:
        try:
            await browser.close()
            browser = None
            logger.info('浏览器已关闭')
        except Exception as e:
            logger.error(f'关闭浏览器时出错: {e}')

async def main():
    """主函数"""
    global message
    
    # 读取账户配置
    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        error_msg = f'读取账户配置失败: {e}'
        logger.error(error_msg)
        return

    # 构建报告
    message += "📊 登录状态报告\\n\\n"
    message += "━━━━━━━━━━━━━━━━━━━━\\n"

    success_count = 0
    total_count = len(accounts)

    for index, account in enumerate(accounts, 1):
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel.lower() else 'Serv00'
        logger.info(f'处理第 {index}/{total_count} 个账户: {serviceName} - {username}')
        
        is_logged_in = await login(username, password, panel)

        now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
        status_icon = "✅" if is_logged_in else "❌"
        status_text = "登录成功" if is_logged_in else "登录失败"
        
        if is_logged_in:
            success_count += 1

        message += (
            f"🔹 服务商: {serviceName}\\n"
            f"👤 账号: {username}\\n"
            f"🕒 时间: {now_beijing}\\n"
            f"{status_icon} 状态: {status_text}\\n"
            "────────────────────\\n"
        )

        # 账户间延迟
        if index < total_count:
            delay = random.randint(2000, 6000)
            await delay_time(delay)

    # 添加统计
    success_rate = (success_count / total_count) * 100
    message += f"\\n📈 统计: 成功 {success_count}/{total_count} (成功率 {success_rate:.1f}%)\\n"
    message += "\\n🏁 所有账号操作已完成"
    
    # 发送报告
    await send_telegram_message(message)
    logger.info(f'任务完成! 成功率: {success_rate:.1f}%')
    
    await shutdown_browser()

async def send_telegram_message(msg):
    """发送Telegram消息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning('跳过Telegram消息发送')
        return
        
    formatted_message = f"""📨 登录状态报告
━━━━━━━━━━━━━━━━━━━━
🕘 时间: {format_to_iso(datetime.utcnow() + timedelta(hours=8))}
━━━━━━━━━━━━━━━━━━━━

{msg}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': formatted_message,
        'parse_mode': 'Markdown',
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            logger.info('Telegram消息发送成功')
        else:
            logger.error(f'Telegram发送失败: {response.status_code}')
    except Exception as e:
        logger.error(f"发送Telegram消息失败: {e}")

if __name__ == '__main__':
    logger.info('开始执行自动化登录脚本')
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f'脚本执行出错: {e}')
        asyncio.run(shutdown_browser())
