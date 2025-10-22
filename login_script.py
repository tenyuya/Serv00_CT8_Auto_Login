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
                    '--disable-gpu',
                    '--window-size=1920,1080'
                ]
            )

        page = await browser.newPage()
        
        # 设置视口大小
        await page.setViewport({'width': 1920, 'height': 1080})
        
        # 设置用户代理
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        url = f'https://{panel}/login/?next=/'
        print(f"正在访问: {url}")
        await page.goto(url, {'waitUntil': 'networkidle2', 'timeout': 30000})

        # 等待页面加载完成 - 根据图片中的结构等待表单
        await page.waitForSelector('form[action="/login/"]', {'timeout': 10000})
        print("表单加载完成")
        
        # 确保页面完全渲染
        await asyncio.sleep(2)

        # 根据图片中的结构，用户名输入框的选择器是 input[name="username"]
        print("正在定位用户名输入框...")
        username_input = await page.waitForSelector('input[name="username"]', {'timeout': 10000})
        if username_input:
            print("找到用户名输入框，开始输入...")
            # 先滚动到元素可见
            await page.evaluate('''(element) => {
                element.scrollIntoView({behavior: 'smooth', block: 'center'});
            }''', username_input)
            
            await asyncio.sleep(1)
            
            # 点击输入框确保焦点
            await username_input.click()
            await asyncio.sleep(0.5)
            
            # 清空输入框
            await page.evaluate('(input) => input.value = ""', username_input)
            await asyncio.sleep(0.5)
            
            # 输入用户名
            await username_input.type(username, {'delay': 50})
            print("用户名输入完成")
        else:
            raise Exception('无法找到用户名输入框')

        # 密码输入框 - 根据图片中的结构
        print("正在定位密码输入框...")
        password_input = await page.waitForSelector('input[name="password"]', {'timeout': 10000})
        if password_input:
            print("找到密码输入框，开始输入...")
            await password_input.click()
            await asyncio.sleep(0.5)
            await password_input.type(password, {'delay': 50})
            print("密码输入完成")
        else:
            raise Exception('无法找到密码输入框')

        # 根据图片中的结构，登录按钮是 button.button.button--primary
        print("正在定位登录按钮...")
        
        # 使用正确的选择器 - 修正了选择器语法
        login_button = await page.waitForSelector('button.button.button--primary', {
            'timeout': 10000
        })
        
        if login_button:
            print("找到登录按钮，准备点击...")
            
            # 滚动到按钮可见
            await page.evaluate('''(element) => {
                element.scrollIntoView({behavior: 'smooth', block: 'center'});
            }''', login_button)
            
            await asyncio.sleep(1)
            
            # 确保按钮可点击
            is_enabled = await page.evaluate('''() => {
                const btn = document.querySelector('button.button.button--primary');
                return btn && !btn.disabled;
            }''')
            
            if not is_enabled:
                print("按钮不可点击，尝试其他方法...")
                # 如果按钮不可点击，尝试通过表单提交
                await page.evaluate('''() => {
                    document.querySelector('form[action="/login/"]').submit();
                }''')
            else:
                # 点击登录按钮
                await login_button.click()
                print("登录按钮已点击，等待响应...")
                
        else:
            # 备用选择器
            login_button = await page.querySelector('button[type="submit"]')
            if login_button:
                await login_button.click()
            else:
                raise Exception('无法找到登录按钮')

        # 等待导航或页面变化
        try:
            # 等待最多20秒的导航
            await asyncio.wait_for(
                page.waitForNavigation({'waitUntil': 'networkidle0', 'timeout': 20000}),
                25
            )
            print("页面导航完成")
        except asyncio.TimeoutError:
            print("导航超时，检查当前页面状态...")
            # 检查是否已经登录成功
            pass

        # 检查登录是否成功 - 多种方式验证
        is_logged_in = await page.evaluate('''() => {
            // 检查登出链接
            const logoutLink = document.querySelector('a[href*="/logout/"]');
            // 检查用户相关元素
            const userElements = document.querySelectorAll('[class*="user"], [class*="account"]');
            // 检查错误消息
            const errorMsg = document.querySelector('.error, .alert-danger, .login-error');
            
            console.log('登录状态检查:');
            console.log('登出链接:', !!logoutLink);
            console.log('用户元素:', userElements.length > 0);
            console.log('错误消息:', !!errorMsg);
            
            // 如果有登出链接或用户元素，并且没有错误消息，则认为登录成功
            return (logoutLink || userElements.length > 0) && !errorMsg;
        }''')

        print(f"登录状态: {'成功' if is_logged_in else '失败'}")
        return is_logged_in

    except Exception as e:
        print(f'{serviceName}账号 {username} 登录时出现错误: {e}')
        # 保存截图用于调试
        try:
            if page:
                screenshot_path = f'error_{username}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
                await page.screenshot({'path': screenshot_path})
                print(f'错误截图已保存: {screenshot_path}')
        except Exception as screenshot_error:
            print(f'保存截图时出错: {screenshot_error}')
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

    successful_logins = 0
    total_accounts = len(accounts)

    for i, account in enumerate(accounts):
        username = account['username']
        password = account['password']
        panel = account['panel']

        serviceName = 'CT8' if 'ct8' in panel else 'Serv00'
        print(f"\n正在处理第 {i+1}/{total_accounts} 个账号: {serviceName} - {username}")
        
        is_logged_in = await login(username, password, panel)
        
        if is_logged_in:
            successful_logins += 1

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

        # 如果不是最后一个账号，添加延迟
        if i < len(accounts) - 1:
            delay = random.randint(3000, 8000)
            print(f"等待 {delay/1000} 秒后处理下一个账号...")
            await delay_time(delay)

    # 添加报告尾部
    success_rate = (successful_logins / total_accounts) * 100
    message += f"\n📈 统计信息:\n"
    message += f"✅ 成功: {successful_logins}/{total_accounts}\n"
    message += f"📊 成功率: {success_rate:.1f}%\n"
    message += "🏁 所有账号操作已完成"

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
        if response.status_code == 200:
            print("Telegram消息发送成功")
        else:
            print(f"发送消息到Telegram失败: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"发送消息到Telegram时出错: {e}")

if __name__ == '__main__':
    asyncio.run(main())
