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

# 全局浏览器实例
browser = None
message = ""

# ------------------ 工具函数 ------------------

def format_to_iso(date):
    return date.strftime('%Y-%m-%d %H:%M:%S')

async def delay_time(ms):
    await asyncio.sleep(ms / 1000)

# ------------------ 登录函数（带重试） ------------------

async def login(username, password, panel, max_retries=2):
    """
    登录 Serv00 / CT8 面板，失败自动重试
    :param username: 用户名
    :param password: 密码
    :param panel: 面板地址
    :param max_retries: 最大重试次数
    :return: True 登录成功 / False 登录失败
    """
    global browser
    serviceName = 'CT8' if 'ct8' in panel.lower() else 'Serv00'

    for attempt in range(1, max_retries + 2):  # 第一次 + 重试次数
        page = None
        try:
            if not browser:
                browser = await launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-blink-features=AutomationControlled'
                    ]
                )

            page = await browser.newPage()
            url = f'https://{panel}/login/?next=/'
            await page.goto(url, {'waitUntil': 'networkidle2'})

            # 等待用户名输入框
            await page.waitForSelector('#id_username', timeout=10000)
            await page.evaluate('(input) => input.value = ""', await page.querySelector('#id_username'))
            await page.type('#id_username', username)
            await page.type('#id_password', password)

            # 等待并点击登录按钮（多选择器匹配）
            button_selectors = [
                '#submit',
                'button[type="submit"]',
                'input[type="submit"]',
                'button.button--primary'
            ]
            login_button = None
            for selector in button_selectors:
                try:
                    await page.waitForSelector(selector, timeout=5000)
                    login_button = await page.querySelector(selector)
                    if login_button:
                        break
                except:
                    continue

            if not login_button:
                await page.screenshot({'path': f'{username}_login_error.png', 'fullPage': True})
                raise Exception('无法找到登录按钮')

            await login_button.click()
            await page.waitForNavigation({'waitUntil': 'networkidle2'})

            # 检查是否登录成功
            is_logged_in = await page.evaluate('''() => {
                return document.querySelector('a[href="/logout/"]') !== null;
            }''')

            if is_logged_in:
                return True
            else:
                raise Exception('登录失败，未检测到登出按钮')

        except Exception as e:
            print(f'{serviceName}账号 {username} 第 {attempt} 次尝试登录失败: {e}')
            if attempt <= max_retries:
                wait_sec = random.randint(1, 3)
                print(f'等待 {wait_sec} 秒后重试...')
                await delay_time(wait_sec * 1000)
            else:
                return False

        finally:
            if page:
                await page.close()

# ------------------ 关闭浏览器 ------------------

async def shutdown_browser():
    global browser
    if browser:
        await browser.close()
        browser = None

# ------------------ Telegram 消息 ------------------

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
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code != 200:
            print(f"发送消息到Telegram失败: {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")

# ------------------ 主函数 ------------------

async def main():
    global message

    # 读取账户信息
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

    # 循环登录每个账号
    for account in accounts:
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel.lower() else 'Serv00'
        is_logged_in = await login(username, password, panel, max_retries=2)

        now_beijing = format_to_iso(datetime.utcnow() + timedelta(hours=8))
        status_icon = "✅" if is_logged_in else "❌"
        status_text = "登录成功" if is_logged_in else "登录失败"

        message += (
            f"🔹 *服务商*: `{serviceName}`\n"
            f"👤 *账号*: `{username}`\n"
            f"🕒 *时间*: {now_beijing}\n"
            f"{status_icon} *状态*: _{status_text}_\n"
            "────────────────────\n"
        )

        # 随机延迟，模拟人操作
        delay = random.randint(1000, 8000)
        await delay_time(delay)

    # 添加报告尾部
    message += "\n🏁 所有账号操作已完成"

    # 发送 Telegram 消息
    await send_telegram_message(message)
    print('所有账号登录完成！')

    # 关闭浏览器
    await shutdown_browser()

# ------------------ 脚本入口 ------------------

if __name__ == '__main__':
    asyncio.run(main())