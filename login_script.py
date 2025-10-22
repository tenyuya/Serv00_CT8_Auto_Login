import json
import asyncio
from pyppeteer import launch
from datetime import datetime, timedelta
import aiofiles
import random
import requests
import os

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

async def login(username, password, panel):
    global browser
    page = None
    serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
    
    try:
        if not browser:
            browser = await launch(
                headless=True, 
                args=[
                    '--no-sandbox', 
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu'
                ]
            )

        page = await browser.newPage()
        
        # 设置视口大小
        await page.setViewport({'width': 1920, 'height': 1080})
        
        # 设置用户代理
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        url = f'https://{panel}/login/?next=/'
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})

        # 等待页面加载完成
        await page.waitForSelector('form[action="/login/"]', {'timeout': 10000})

        # 输入用户名 - 根据图片中的结构修正选择器
        username_input = await page.querySelector('input[name="username"]')
        if username_input:
            # 先点击输入框确保焦点
            await username_input.click()
            # 清空输入框
            await page.evaluate('(input) => input.value = ""', username_input)
            # 输入用户名
            await username_input.type(username)
            await asyncio.sleep(1)  # 短暂延迟确保输入完成
        else:
            raise Exception('无法找到用户名输入框')

        # 输入密码
        password_input = await page.querySelector('input[name="password"]')
        if password_input:
            await password_input.click()
            await password_input.type(password)
            await asyncio.sleep(1)
        else:
            raise Exception('无法找到密码输入框')

        # 根据图片中的结构，登录按钮是 <button type="submit" class="button button--primary">
        login_button = await page.querySelector('button.button.button--primary[type="submit"]')
        if not login_button:
            # 如果上面的选择器找不到，尝试其他可能的选择器
            login_button = await page.querySelector('button[type="submit"]')
        
        if login_button:
            # 等待按钮可点击
            await page.waitForFunction(
                '''() => {
                    const btn = document.querySelector('button.button.button--primary[type="submit"]') || 
                              document.querySelector('button[type="submit"]');
                    return btn && !btn.disabled;
                }''',
                {'timeout': 5000}
            )
            
            # 点击登录按钮
            await login_button.click()
            
            # 等待导航或页面变化
            try:
                await page.waitForNavigation({'waitUntil': 'networkidle0', 'timeout': 15000})
            except:
                # 如果导航没有发生，等待页面内容变化
                await page.waitForFunction(
                    '''() => {
                        return !document.querySelector('form[action="/login/"]') || 
                               document.querySelector('a[href="/logout/"]');
                    }''',
                    {'timeout': 10000}
                )
        else:
            raise Exception('无法找到登录按钮')

        # 检查登录是否成功 - 查找登出链接或其他登录成功标识
        is_logged_in = await page.evaluate('''() => {
            const logoutLink = document.querySelector('a[href="/logout/"]');
            const errorMessage = document.querySelector('.error');
            return !!logoutLink && !errorMessage;
        }''')

        return is_logged_in

    except Exception as e:
        print(f'{serviceName}账号 {username} 登录时出现错误: {e}')
        # 可以添加截图功能用于调试
        # if page:
        #     await page.screenshot({'path': f'error_{username}.png'})
        return False

    finally:
        if page:
            await page.close()

async def shutdown_browser():
    global browser
    if browser:
        await browser.close()
        browser = None

async def main():
    global message

    try:
        async with aiofiles.open('accounts.json', mode='r', encoding='utf-8') as f:
            accounts_json = await f.read()
        accounts = json.loads(accounts_json)
    except Exception as e:
        print(f'读取 accounts.json 文件时出错: {e}')
        return

    # 添加报告头部
    message += "📊 登录状态报告\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n"

    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
        is_logged_in = await login(username, password, panel)

        now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
        status_icon = "✅" if is_logged_in else "❌"
        status_text = "登录成功" if is_logged_in else "登录失败"

        message += (
            f"🔹 服务商: {serviceName}\n"
            f"👤 账号: {username}\n"
            f"🕒 时间: {now_beijing}\n"
            f"{status_icon} 状态: {status_text}\n"
            "────────────────────\n"
        )

        # 随机延迟，避免请求过于频繁
        delay = random.randint(2000, 10000)
        await delay_time(delay)

    # 添加报告尾部
    message += "\n🏁 所有账号操作已完成"
    await send_telegram_message(message)
    print('所有账号登录完成！')
    await shutdown_browser()

async def send_telegram_message(message):
    formatted_message = f"""
📨 Serv00 & CT8 保号脚本运行报告
━━━━━━━━━━━━━━━━━━━━
🕘 北京时间: {format_to_iso(datetime.utcnow() + timedelta(hours=8))}
🌐 UTC时间: {format_to_iso(datetime.utcnow())}
━━━━━━━━━━━━━━━━━━━━

{message}
"""

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': formatted_message,
        'parse_mode': 'Markdown',
    }
    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"发送消息到Telegram失败: {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
