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
        # 移除自动化检测特征
        import pyppeteer
        if hasattr(pyppeteer, 'launcher') and hasattr(pyppeteer.launcher, 'DEFAULT_ARGS'):
            original_args = pyppeteer.launcher.DEFAULT_ARGS
            pyppeteer.launcher.DEFAULT_ARGS = [
                arg for arg in original_args 
                if arg != '--enable-automation' and not arg.startswith('--enable-automation')
            ]
        
        browser = await launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--window-size=1920,1080',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ],
            ignoreHTTPSErrors=True,
            autoClose=False
        )
    return browser

async def login(username, password, panel):
    """基于实际页面结构的登录函数"""
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
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
        }''')
        
        await page.setViewport({'width': 1920, 'height': 1080})
        
        # 拦截图片和样式表以加快加载速度
        await page.setRequestInterception(True)
        
        async def intercept_request(req):
            if req.resourceType() in ['image', 'stylesheet', 'font']:
                await req.abort()
            else:
                await req.continue_()
        
        page.on('request', lambda req: asyncio.ensure_future(intercept_request(req)))
        
        url = f'https://{panel}/login/?next=/'
        logger.info(f'正在访问: {url} - 账号: {username}')
        
        # 导航到登录页面
        try:
            await page.goto(url, {'waitUntil': 'domcontentloaded', 'timeout': 30000})
        except Exception as e:
            logger.warning(f'页面加载超时，但继续执行: {e}')
        
        # 等待关键元素加载
        try:
            await page.waitForSelector('#id_username', {'timeout': 15000})
            logger.info('找到用户名输入框')
        except Exception as e:
            logger.error(f'等待用户名输入框超时: {e}')
            # 尝试保存截图用于调试
            try:
                await page.screenshot({'path': f'debug_no_username_{serviceName}_{username}.png'})
            except:
                pass
            return False

        # 输入用户名
        try:
            username_input = await page.querySelector('#id_username')
            if username_input:
                # 点击输入框获取焦点
                await username_input.click()
                await asyncio.sleep(0.3)
                
                # 清空输入框内容
                await page.evaluate('''(input) => {
                    input.value = '';
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }''', username_input)
                
                # 模拟人类输入
                for char in username:
                    await username_input.press(char)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                
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
                await page.evaluate('''(input) => {
                    input.value = '';
                }''', password_input)
                
                # 模拟人类输入密码
                for char in password:
                    await password_input.press(char)
                    await asyncio.sleep(random.uniform(0.05, 0.15))
                
                logger.info('密码输入完成')
        except Exception as e:
            logger.error(f'输入密码时出错: {e}')
            return False

        # 基于图片中的实际HTML结构查找登录按钮
        # 根据图片，按钮结构是: <button type="submit" class="button button--primary">
        login_button = None
        button_selectors = [
            'button.button--primary[type="submit"]',  # 最精确的选择器
            'button[type="submit"].button--primary',
            '.login-form__button button',
            'button.button--primary',
            'button[type="submit"]',
            'input[type="submit"]',
            '.button--primary'
        ]
        
        for selector in button_selectors:
            try:
                login_button = await page.querySelector(selector)
                if login_button:
                    # 验证按钮是否可见和包含正确文本
                    is_visible = await page.evaluate('''(button) => {
                        const rect = button.getBoundingClientRect();
                        const style = window.getComputedStyle(button);
                        return rect.width > 0 && rect.height > 0 && 
                               style.visibility !== 'hidden' &&
                               style.display !== 'none';
                    }''', login_button)
                    
                    if is_visible:
                        logger.info(f'使用选择器找到可见按钮: {selector}')
                        break
                    else:
                        login_button = None
                        logger.info(f'选择器找到按钮但不可见: {selector}')
            except Exception as e:
                logger.debug(f'选择器 {selector} 失败: {e}')
                continue

        # 如果通过选择器没找到，尝试通过文本查找
        if not login_button:
            try:
                buttons = await page.querySelectorAll('button')
                for button in buttons:
                    button_text = await page.evaluate('(button) => button.textContent', button)
                    if button_text and any(text in button_text.lower() for text in ['sign in', 'login', '登录', '登入']):
                        login_button = button
                        logger.info('通过按钮文本找到登录按钮')
                        break
            except Exception as e:
                logger.debug(f'通过文本查找按钮失败: {e}')

        if not login_button:
            logger.error('无法找到有效的登录按钮')
            # 保存当前页面HTML用于调试
            try:
                html_content = await page.content()
                with open(f'debug_page_{serviceName}_{username}.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                await page.screenshot({'path': f'debug_no_button_{serviceName}_{username}.png', 'fullPage': True})
            except Exception as debug_e:
                logger.error(f'保存调试信息失败: {debug_e}')
            return False

        # 确保按钮在视图中
        await page.evaluate('''(button) => {
            button.scrollIntoView({ 
                block: 'center', 
                behavior: 'instant' 
            });
        }''', login_button)
        
        # 模拟人类操作延迟
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        # 点击按钮
        try:
            await login_button.click()
            logger.info('登录按钮点击完成')
        except Exception as e:
            # 如果常规点击失败，尝试JavaScript点击
            logger.warning(f'常规点击失败，尝试JS点击: {e}')
            await page.evaluate('(button) => button.click()', login_button)

        # 等待登录结果
        logger.info('等待登录处理...')
        
        # 设置较长的超时时间，等待可能的AJAX登录
        await asyncio.sleep(5)
        
        # 检查是否发生了页面跳转
        current_url = await page.evaluate('window.location.href')
        logger.info(f'当前URL: {current_url}')
        
        # 多种方式验证登录是否成功
        is_logged_in = await page.evaluate('''() => {
            // 1. 检查是否有登出链接
            const logoutSelectors = [
                'a[href*="/logout/"]',
                'a[href*="logout"]',
                '[href*="/logout/"]',
                'a:contains("Logout")',
                'a:contains("Sign out")',
                'a:contains("登出")'
            ];
            
            for (const selector of logoutSelectors) {
                try {
                    const element = document.querySelector(selector);
                    if (element) return true;
                } catch (e) {}
            }
            
            // 2. 检查页面内容关键词
            const bodyText = document.body.innerText.toLowerCase();
            const successKeywords = ['dashboard', 'panel', 'overview', 'welcome', '控制面板', '主页'];
            const failureKeywords = ['login', 'sign in', '登录', 'invalid', 'error'];
            
            for (const keyword of successKeywords) {
                if (bodyText.includes(keyword) && !bodyText.includes('login')) {
                    return true;
                }
            }
            
            // 3. 检查URL是否包含成功指示
            const url = window.location.href.toLowerCase();
            if (url.includes('/dashboard') || url.includes('/panel') || 
                (!url.includes('/login') && url.endsWith('/'))) {
                return true;
            }
            
            // 4. 检查是否有用户相关的元素
            const userElements = document.querySelectorAll([
                '[class*="user"]',
                '[class*="account"]', 
                '[class*="profile"]',
                '.username',
                '.user-info'
            ].join(','));
            
            if (userElements.length > 0) {
                return true;
            }
            
            return false;
        }''')
        
        # 额外检查：如果仍在登录页面且有错误消息，则登录失败
        if not is_logged_in and '/login' in current_url:
            error_msg = await page.evaluate('''() => {
                const errorSelectors = [
                    '.error',
                    '.alert-danger',
                    '.text-danger',
                    '[class*="error"]',
                    '[class*="invalid"]'
                ];
                
                for (const selector of errorSelectors) {
                    const element = document.querySelector(selector);
                    if (element && element.textContent.trim()) {
                        return element.textContent.trim();
                    }
                }
                return null;
            }''')
            
            if error_msg:
                logger.error(f'登录错误: {error_msg}')
                is_logged_in = False
            else:
                # 没有错误消息但仍在登录页面，可能是其他问题
                logger.warning('仍在登录页面但未发现明显错误消息')
                is_logged_in = False
        elif not is_logged_in:
            # 不在登录页面但验证失败，可能是验证逻辑问题，尝试更宽松的判断
            logger.warning('登录验证失败，但已离开登录页面，尝试宽松验证')
            is_logged_in = await page.evaluate('''() => {
                // 宽松验证：只要不在登录页面且没有明显错误就认为成功
                return !document.querySelector('input[type="password"]') && 
                       !document.body.innerText.toLowerCase().includes('sign in');
            }''')

        logger.info(f'{serviceName}账号 {username} 登录{"成功" if is_logged_in else "失败"}')
        return is_logged_in
        
    except Exception as e:
        logger.error(f'{serviceName}账号 {username} 登录时出现错误: {str(e)}')
        
        # 保存错误截图和HTML用于调试
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            await page.screenshot({'path': f'error_{serviceName}_{username}_{timestamp}.png', 'fullPage': True})
            html_content = await page.content()
            with open(f'error_{serviceName}_{username}_{timestamp}.html', 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f'错误信息已保存: error_{serviceName}_{username}_{timestamp}.png/html')
        except Exception as debug_e:
            logger.error(f'保存调试信息失败: {debug_e}')
            
        return False
        
    finally:
        if page:
            await page.close()

async def shutdown_browser():
    """关闭浏览器实例"""
    global browser
    if browser:
        try:
            # 获取所有打开的页面并关闭
            pages = await browser.pages()
            for page in pages:
                try:
                    await page.close()
                except:
                    pass
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
            
    except json.JSONDecodeError as e:
        error_msg = f'accounts.json 文件格式错误: {e}'
        logger.error(error_msg)
        await send_telegram_message(error_msg)
        return
    except Exception as e:
        error_msg = f'读取 accounts.json 文件时出错: {e}'
        logger.error(error_msg)
        await send_telegram_message(error_msg)
        return

    # 添加报告头部
    message += "📊 登录状态报告\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n"

    success_count = 0
    total_count = len(accounts)
    detailed_results = []

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

        account_result = (
            f"🔹 服务商: {serviceName}\n"
            f"👤 账号: {username}\n"
            f"🕒 时间: {now_beijing}\n"
            f"{status_icon} 状态: {status_text}\n"
            "────────────────────\n"
        )
        
        message += account_result
        detailed_results.append(account_result)

        # 在账户之间添加随机延迟（最后一个账户不延迟）
        if index < total_count:
            delay = random.randint(3000, 8000)
            logger.info(f'等待 {delay/1000} 秒后处理下一个账户...')
            await delay_time(delay)

    # 添加统计信息
    success_rate = (success_count / total_count) * 100 if total_count > 0 else 0
    
    message += f"\n📈 统计信息:\n"
    message += f"✅ 成功: {success_count}/{total_count}\n"
    message += f"📊 成功率: {success_rate:.1f}%\n"
    
    if success_rate == 100:
        message += "🎉 所有账户登录成功！\n"
    elif success_rate >= 80:
        message += "👍 大部分账户登录成功！\n"
    elif success_rate > 0:
        message += "⚠️  部分账户登录失败，请检查配置。\n"
    else:
        message += "❌ 所有账户登录失败，请检查网络和账户配置。\n"
    
    message += "\n🏁 所有账号操作已完成"
    
    # 发送报告
    await send_telegram_message(message)
    logger.info(f'所有账号登录完成！成功率: {success_rate:.1f}%')
    
    await shutdown_browser()

async def send_telegram_message(msg):
    """发送Telegram消息"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning('未设置Telegram环境变量，跳过消息发送')
        return
        
    formatted_message = f"""
📨 Serv00 & CT8 保号脚本运行报告
━━━━━━━━━━━━━━━━━━━━
🕘 北京时间: {format_to_iso(datetime.utcnow() + timedelta(hours=8))}
🌐 UTC时间: {format_to_iso(datetime.utcnow())}
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
        asyncio.run(shutdown_browser())
    logger.info('脚本执行结束')
