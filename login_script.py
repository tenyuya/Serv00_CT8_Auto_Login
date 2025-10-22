import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta, timezone
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
    """初始化浏览器实例"""
    global browser
    if not browser:
        # 移除自动化检测特征
        import pyppeteer
        if hasattr(pyppeteer, 'launcher') and hasattr(pyppeteer.launcher, 'DEFAULT_ARGS'):
            original_args = pyppeteer.launcher.DEFAULT_ARGS
            filtered_args = []
            for arg in original_args:
                if arg != '--enable-automation' and not arg.startswith('--enable-automation'):
                    filtered_args.append(arg)
            pyppeteer.launcher.DEFAULT_ARGS = filtered_args
        
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080',
            ],
            ignoreHTTPSErrors=True
        )
    return browser

async def login(username, password, panel):
    """修复按钮点击问题的登录函数"""
    global browser
    page = None
    serviceName = 'CT8' if 'ct8' in panel.lower() else 'Serv00'
    
    try:
        # 初始化浏览器
        browser = await init_browser()
        page = await browser.newPage()
        
        # 设置反检测
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # 隐藏webdriver属性
        await page.evaluateOnNewDocument('''() => {
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        }''')
        
        await page.setViewport({'width': 1920, 'height': 1080})
        
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
                # 清空并输入用户名
                await username_input.click()
                await page.evaluate('(input) => input.value = ""', username_input)
                await username_input.type(username, {'delay': random.randint(30, 80)})
                logger.info('用户名输入完成')
        except Exception as e:
            logger.error(f'输入用户名时出错: {e}')
            return False

        # 输入密码
        try:
            password_input = await page.querySelector('#id_password')
            if password_input:
                await password_input.click()
                await page.evaluate('(input) => input.value = ""', password_input)
                await password_input.type(password, {'delay': random.randint(30, 80)})
                logger.info('密码输入完成')
        except Exception as e:
            logger.error(f'输入密码时出错: {e}')
            return False

        # 修复按钮点击问题 - 使用JavaScript直接点击
        login_button = None
        button_selectors = [
            'button.button--primary[type="submit"]',
            'button[type="submit"].button--primary',
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

        # 修复按钮点击问题 - 使用JavaScript直接执行点击
        try:
            # 方法1: 使用JavaScript直接点击，避免可见性检查
            await page.evaluate('''(button) => {
                button.click();
            }''', login_button)
            logger.info('使用JavaScript点击按钮成功')
        except Exception as e:
            logger.error(f'JavaScript点击失败: {e}')
            # 方法2: 如果JS点击失败，尝试常规点击
            try:
                await login_button.click()
                logger.info('常规点击按钮成功')
            except Exception as e2:
                logger.error(f'常规点击也失败: {e2}')
                return False

        # 等待登录处理
        logger.info('等待登录处理...')
        await asyncio.sleep(5)
        
        # 检查登录是否成功
        current_url = await page.evaluate('window.location.href')
        logger.info(f'当前URL: {current_url}')
        
        # 多种方式验证登录状态
        is_logged_in = await page.evaluate('''() => {
            // 检查登出链接
            const logoutLinks = [
                document.querySelector('a[href*="/logout/"]'),
                document.querySelector('a[href*="logout"]')
            ].find(link => link !== null);
            
            // 检查页面内容
            const bodyText = document.body.innerText.toLowerCase();
            const hasDashboard = bodyText.includes('dashboard') || 
                                bodyText.includes('控制面板') ||
                                bodyText.includes('welcome');
            
            // 检查用户相关元素
            const userElements = document.querySelectorAll('[class*="user"], [class*="account"]');
            
            return !!logoutLinks || hasDashboard || userElements.length > 0;
        }''')
        
        # 额外检查：如果仍在登录页面，则登录失败
        if '/login' in current_url:
            logger.info('检测到仍在登录页面，登录失败')
            is_logged_in = False

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
        if not os.path.exists('accounts.json'):
            error_msg = 'accounts.json 文件不存在'
            logger.error(error_msg)
            await send_telegram_message(error_msg)
            return
            
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
        
        if not accounts:
            error_msg = 'accounts.json 中没有找到账户配置'
            logger.error(error_msg)
            await send_telegram_message(error_msg)
            return
            
    except Exception as e:
        error_msg = f'读取配置文件时出错: {e}'
        logger.error(error_msg)
        await send_telegram_message(error_msg)
        return

    # 添加报告头部
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

        # 使用时区安全的时间获取方式
        utc_now = datetime.now(timezone.utc)
        beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
        now_beijing = format_to_iso(beijing_time)
        
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

        # 在账户之间添加随机延迟
        if index < total_count:
            delay = random.randint(2000, 6000)
            logger.info(f'等待 {delay/1000} 秒后处理下一个账户...')
            await delay_time(delay)

    # 添加统计信息
    success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
    
    message += f"\\n📈 统计信息:\\n"
    message += f"✅ 成功: {success_count}/{total_count}\\n"
    message += f"📊 成功率: {success_rate:.1f}%\\n"
    message += "\\n🏁 所有账号操作已完成"
    
    # 发送报告
    await send_telegram_message(message)
    logger.info(f'所有账号登录完成！成功率: {success_rate:.1f}%')
    
    await shutdown_browser()

async def send_telegram_message(msg):
    """发送Telegram消息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning('未设置Telegram环境变量，跳过消息发送')
        return
        
    # 使用时区安全的时间获取方式
    utc_now = datetime.now(timezone.utc)
    beijing_time = utc_now.astimezone(timezone(timedelta(hours=8)))
    
    formatted_message = f"""
📨 Serv00 & CT8 保号脚本运行报告
━━━━━━━━━━━━━━━━━━━━
🕘 北京时间: {format_to_iso(beijing_time)}
🌐 UTC时间: {format_to_iso(utc_now)}
━━━━━━━━━━━━━━━━━━━━

{msg}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': formatted_message,
        'parse_mode': 'Markdown',
    }
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            logger.info('Telegram消息发送成功')
        else:
            logger.error(f'发送Telegram消息失败: {response.status_code} - {response.text}')
    except Exception as e:
        logger.error(f"发送Telegram消息时出错: {e}")

if __name__ == '__main__':
    logger.info('开始执行自动化登录脚本...')
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('用户中断脚本执行')
    except Exception as e:
        logger.error(f'脚本执行出错: {e}')
    finally:
        asyncio.run(shutdown_browser())
    logger.info('脚本执行结束')
