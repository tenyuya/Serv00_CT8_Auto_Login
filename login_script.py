import os
import json
import time
import logging
import requests
import sys
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from datetime import datetime, timedelta
import random
# -------------------- 日志配置 --------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
# -------------------- Telegram 消息 --------------------
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
def format_to_iso(dt: datetime):
    return dt.strftime('%Y-%m-%d %H:%M:%S')
def send_telegram_message(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("⚠️ Telegram环境变量未设置，跳过通知")
        return False
    formatted_message = f"""📨 Serv00 & CT8
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
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Telegram消息发送成功")
        else:
            logger.error(f"❌ 发送消息失败: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"❌ 发送消息异常: {e}")
# -------------------- 登录机器人 --------------------
class Serv00LoginBot:
    def __init__(self):
        self.driver = None
        self.wait = None
        headless_env = os.environ.get('HEADLESS', 'true').lower()
        self.headless = headless_env in ['1', 'true', 'yes']
    def setup_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            try:
                self.driver.execute_cdp_cmd(
                    "Page.addScriptToEvaluateOnNewDocument",
                    {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
                )
            except Exception:
                pass
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("✅ 浏览器驱动设置完成 (headless=%s)", self.headless)
            return True
        except Exception as e:
            logger.error(f"❌ 浏览器驱动设置失败: {e}")
            return False
    def wait_for_element(self, by, value, timeout=15):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            logger.debug(f"元素定位超时: {by}={value}")
            return None
    def wait_for_element_clickable(self, by, value, timeout=15):
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            logger.debug(f"元素不可点击: {by}={value}")
            return None
    def safe_click(self, element):
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.error(f"❌ 点击失败: {e}")
            return False
    def safe_send_keys(self, element, text):
        try:
            element.clear()
            element.send_keys(text)
            return True
        except Exception as e:
            logger.error(f"❌ 输入失败: {e}")
            return False
    def take_screenshot(self, name):
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"📸 截图已保存: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ 截图失败: {e}")
            return None
    def build_candidate_urls(self, panel_value):
        candidates = []
        if not panel_value:
            return candidates
        panel_value = panel_value.strip()
        if panel_value.startswith('http://') or panel_value.startswith('https://'):
            candidates.append(panel_value)
            candidates.append(panel_value.rstrip('/') + '/login')
            candidates.append(panel_value.rstrip('/') + '/admin/login')
        else:
            candidates.extend([
                panel_value,
                'https://' + panel_value,
                'http://' + panel_value,
                'https://' + panel_value + '/login',
                'https://' + panel_value + '/admin/login',
                'http://' + panel_value + '/login',
                'http://' + panel_value + '/admin/login'
            ])
        # 去重
        seen = set()
        unique = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique
    def login_to_serv00(self, account_info):
        name = account_info.get('name') or account_info.get('username') or account_info.get('panel') or '未知账号'
        panel = account_info.get('panel') or account_info.get('url') or account_info.get('host') or ''
        username = account_info.get('username') or account_info.get('user') or ''
        password = account_info.get('password') or account_info.get('pass') or ''
        if not panel or not username or not password:
            logger.error(f"❌ 账号信息不完整: {name} (panel、username、password 三项必需)")
            return False, "账号信息不完整"
        logger.info(f"🔐 开始处理账号: {name} (用户名: {username})")
        url_candidates = self.build_candidate_urls(panel)
        logger.debug(f"候选登录页: {url_candidates}")
        for url in url_candidates:
            try:
                logger.info(f"🌐 尝试访问: {url}")
                try:
                    self.driver.get(url)
                except Exception as e:
                    logger.debug(f"访问 {url} 失败: {e}")
                    continue
                time.sleep(2)
                username_field = self.wait_for_element(By.NAME, "login", timeout=4) or \
                                 self.wait_for_element(By.NAME, "username", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[type='text']", timeout=4) or \
                                 self.wait_for_element(By.ID, "username", timeout=4)
                if not username_field:
                    logger.debug(f"在 {url} 未找到用户名输入框，尝试下一个候选页")
                    continue
                if not self.safe_send_keys(username_field, username):
                    self.take_screenshot(f"error_username_input_{name}")
                    return False, "用户名输入失败"
                logger.info("✅ 用户名输入完成")
                time.sleep(0.5)
                password_field = self.wait_for_element(By.NAME, "password", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[type='password']", timeout=4) or \
                                 self.wait_for_element(By.ID, "password", timeout=4)
                if not password_field:
                    self.take_screenshot(f"error_password_not_found_{name}")
                    return False, "未找到密码输入框"
                if not self.safe_send_keys(password_field, password):
                    self.take_screenshot(f"error_password_input_{name}")
                    return False, "密码输入失败"
                logger.info("✅ 密码输入完成")
                time.sleep(0.5)
                login_button = self.wait_for_element_clickable(By.CSS_SELECTOR, "button[type='submit']", timeout=4) or \
                               self.wait_for_element_clickable(By.CSS_SELECTOR, "button.btn-primary", timeout=4)
                if not login_button:
                    logger.debug("未找到登录按钮，尝试回车提交")
                    try:
                        password_field.send_keys("\n")
                    except Exception:
                        logger.debug("回车提交失败")
                else:
                    logger.info("🖱️ 点击登录按钮...")
                    if not self.safe_click(login_button):
                        self.take_screenshot(f"error_click_failed_{name}")
                        return False, "登录按钮点击失败"
                time.sleep(5)
                current_url = self.driver.current_url or ''
                page_title = (self.driver.title or '').lower()
                page_source = (self.driver.page_source or '').lower()
                success_indicators = ['dashboard', 'panel', 'account', 'welcome', 'strona główna', 'logged', 'profile']
                error_indicators = ['error', 'błąd', 'invalid', 'failed', 'unauthorized', 'forbidden']
                if any(ind in current_url.lower() for ind in success_indicators) \
                   or any(ind in page_title for ind in success_indicators) \
                   or any(ind in page_source for ind in success_indicators):
                    logger.info(f"✅ {name} 登录成功! (URL: {current_url})")
                    self.take_screenshot(f"success_{name}")
                    return True, "登录成功"
                if any(ind in page_source for ind in error_indicators):
                    logger.error(f"❌ {name} 登录失败: 页面包含错误信息")
                    self.take_screenshot(f"error_page_{name}")
                    return False, "页面错误信息"
                logger.info(f"⚠️ {name} 登录状态未知，但在 {url} 已尝试提交，当前 URL: {current_url}")
                self.take_screenshot(f"unknown_{name}")
                return True, "页面跳转完成"
            except Exception as e:
                logger.error(f"❌ 在尝试 {url} 登录时出现异常: {e}")
                continue
        logger.error(f"❌ 所有候选登录页都尝试失败: {panel}")
        self.take_screenshot(f"error_all_candidates_{name}")
        return False, "无法找到合适的登录页面或登录失败"
    def process_all_accounts(self):
        accounts_json = os.environ.get('ACCOUNTS_JSON', '[]')
        logger.info("📦 读取 ACCOUNTS_JSON（已屏蔽密码）")
        try:
            accounts = json.loads(accounts_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ 账号JSON格式错误: {e}")
            return False
        if not accounts:
            logger.error("❌ 未找到账号配置")
            return False
        usernames = [a.get('username') or a.get('user') or '' for a in accounts]
        logger.info(f"📋 找到 {len(accounts)} 个账号需要处理, 用户名列表: {usernames}")
        if not self.setup_driver():
            return False
        results = []
        try:
            for i, account in enumerate(accounts, 1):
                short_name = account.get('name') or account.get('username') or account.get('panel') or f'账号{i}'
                logger.info(f"🔄 处理第 {i}/{len(accounts)} 个账号: {short_name}")
                success, message = self.login_to_serv00(account)
                results.append({
                    'name': short_name,
                    'success': success,
                    'message': message,
                    'panel': account.get('panel', '')
                })
                if i < len(accounts):
                    wait_time = random.randint(3, 8)
                    logger.info(f"⏳ 等待 {wait_time} 秒后处理下一个账号...")
                    time.sleep(wait_time)
            # 构造 Telegram 消息
            message_lines = []
            success_count = sum(1 for r in results if r['success'])
            success_rate = (success_count / len(results)) * 100
            message_lines.append(
                f"📊 统计信息:\n✅ 成功: {success_count}/{len(results)}\n📈 成功率: {success_rate:.1f}%\n🏁 所有账号操作已完成"
            )
            send_telegram_message("\n".join(message_lines))
            return success_count > 0
        except Exception as e:
            logger.error(f"❌ 处理过程中出现异常: {e}")
            send_telegram_message(f"❌ Serv00 & CT8 登录任务失败\n\n错误: {e}")
            return False
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                logger.info("🚪 浏览器已关闭")
# -------------------- 主函数 --------------------
def main():
    logger.info("🚀 开始执行 Serv00 & CT8 自动登录脚本")
    bot = Serv00LoginBot()
    success = bot.process_all_accounts()
    if success:
        logger.info("✨ 脚本执行完成")
        sys.exit(0)
    else:
        logger.error("💥 脚本执行失败")
        sys.exit(1)
if __name__ == "__main__":
    main()
