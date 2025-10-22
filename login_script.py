import os
import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException
from selenium.webdriver.chrome.options import Options
import requests
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class Serv00LoginBot:
    def __init__(self):
        self.driver = None
        self.wait = None
        # 从环境读取是否启用无头模式，默认 true
        headless_env = os.environ.get('HEADLESS', 'true').lower()
        self.headless = headless_env in ['1', 'true', 'yes']
        
    def setup_driver(self):
        """设置浏览器驱动（适配GitHub Actions）"""
        chrome_options = Options()
        
        # GitHub Actions / 无头环境配置
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        if self.headless:
            chrome_options.add_argument('--headless=new')  # 使用 newer headless 标志
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 反自动化检测
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            # 直接使用系统上可用的 chromedriver（二进制应由 workflow 提供或 chromedriver-binary-auto 管理）
            self.driver = webdriver.Chrome(options=chrome_options)
            # 解除 webdriver 标志
            try:
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                })
            except Exception:
                # 部分 chromedriver 版本不支持 execute_cdp_cmd，继续也没关系
                pass
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("✅ 浏览器驱动设置完成 (headless=%s)", self.headless)
            return True
        except Exception as e:
            logger.error(f"❌ 浏览器驱动设置失败: {e}")
            return False
    
    def wait_for_element(self, by, value, timeout=15):
        """等待元素出现"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
        except TimeoutException:
            logger.debug(f"元素定位超时: {by}={value}")
            return None
    
    def wait_for_element_clickable(self, by, value, timeout=15):
        """等待元素可点击"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            logger.debug(f"元素不可点击: {by}={value}")
            return None
    
    def safe_click(self, element):
        """安全点击"""
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception as e:
            logger.error(f"❌ 点击失败: {e}")
            return False
    
    def safe_send_keys(self, element, text):
        """安全输入"""
        try:
            element.clear()
            element.send_keys(text)
            return True
        except Exception as e:
            logger.error(f"❌ 输入失败: {e}")
            return False
    
    def take_screenshot(self, name):
        """截图"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            self.driver.save_screenshot(filename)
            logger.info(f"📸 截图已保存: {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ 截图失败: {e}")
            return None
    
    def send_telegram_message(self, message):
        """发送Telegram通知"""
        try:
            bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
            chat_id = os.environ.get('TELEGRAM_CHAT_ID')
            
            if not bot_token or not chat_id:
                logger.warning("⚠️ Telegram环境变量未设置，跳过通知")
                return False
            
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                logger.info("✅ Telegram消息发送成功")
                return True
            else:
                logger.error(f"❌ Telegram消息发送失败: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Telegram消息发送异常: {e}")
            return False
    
    def build_candidate_urls(self, panel_value):
        """根据 panel 字段构造一组候选 URL 来尝试访问登录页"""
        candidates = []
        if not panel_value:
            return candidates
        panel_value = panel_value.strip()
        # 如果看起来像完整 URL，则优先使用
        if panel_value.startswith('http://') or panel_value.startswith('https://'):
            candidates.append(panel_value)
            if panel_value.endswith('/'):
                candidates.append(panel_value + 'login')
            else:
                candidates.append(panel_value + '/login')
            # 也尝试 /admin/login
            if panel_value.endswith('/'):
                candidates.append(panel_value + 'admin/login')
            else:
                candidates.append(panel_value + '/admin/login')
        else:
            # 尝试直接作为主机名或域名
            candidates.append(panel_value)  # 直接尝试 panel（有时包含协议）
            candidates.append('https://' + panel_value)
            candidates.append('http://' + panel_value)
            candidates.append('https://' + panel_value + '/login')
            candidates.append('https://' + panel_value + '/admin/login')
            candidates.append('http://' + panel_value + '/login')
            candidates.append('http://' + panel_value + '/admin/login')
        # 去重并返回
        seen = set()
        unique = []
        for u in candidates:
            if u not in seen:
                seen.add(u)
                unique.append(u)
        return unique
    
    def login_to_serv00(self, account_info):
        """执行登录流程，支持 panel/username/password 结构"""
        # 尽量从多种键中读取字段（向后兼容）
        name = account_info.get('name') or account_info.get('username') or account_info.get('panel') or '未知账号'
        panel = account_info.get('panel') or account_info.get('url') or account_info.get('host') or ''
        username = account_info.get('username') or account_info.get('user') or ''
        password = account_info.get('password') or account_info.get('pass') or ''
        
        # 基础校验
        if not panel or not username or not password:
            logger.error(f"❌ 账号信息不完整: {name} (panel、username、password 三项必需)")
            return False, "账号信息不完整"
        
        logger.info(f"🔐 开始处理账号: {name} (用户名: {username})")
        
        # 构造待尝试 URL 列表
        url_candidates = self.build_candidate_urls(panel)
        logger.debug(f"候选登录页: {url_candidates}")
        
        for url in url_candidates:
            try:
                logger.info(f"🌐 尝试访问: {url}")
                # 尝试访问 URL
                try:
                    self.driver.get(url)
                except Exception as e:
                    logger.debug(f"访问 {url} 失败: {e}")
                    continue  # 尝试下一个 URL
                time.sleep(2)  # 等待页面加载
                
                # 尝试找用户名输入框（支持多种选择器）
                username_field = self.wait_for_element(By.NAME, "login", timeout=4) or \
                                 self.wait_for_element(By.NAME, "username", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[type='text']", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[name='login']", timeout=4) or \
                                 self.wait_for_element(By.ID, "username", timeout=4) or \
                                 self.wait_for_element(By.ID, "login", timeout=4)
                
                # 如果没有找到用户名框，说明当前页面可能不是登录页，尝试其他候选 URL
                if not username_field:
                    logger.debug(f"在 {url} 未找到用户名输入框，尝试下一个候选页")
                    continue
                
                # 找到用户名框则进行后续操作
                if not self.safe_send_keys(username_field, username):
                    self.take_screenshot(f"error_username_input_{name}")
                    return False, "用户名输入失败"
                logger.info("✅ 用户名输入完成")
                time.sleep(0.5)
                
                # 查找密码输入框
                password_field = self.wait_for_element(By.NAME, "password", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[type='password']", timeout=4) or \
                                 self.wait_for_element(By.CSS_SELECTOR, "input[name='password']", timeout=4) or \
                                 self.wait_for_element(By.ID, "password", timeout=4)
                
                if not password_field:
                    self.take_screenshot(f"error_password_not_found_{name}")
                    return False, "未找到密码输入框"
                
                if not self.safe_send_keys(password_field, password):
                    self.take_screenshot(f"error_password_input_{name}")
                    return False, "密码输入失败"
                logger.info("✅ 密码输入完成")
                time.sleep(0.5)
                
                # 查找登录按钮（多种可能）
                login_button = self.wait_for_element_clickable(By.CSS_SELECTOR, "button[type='submit']", timeout=4) or \
                               self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='submit']", timeout=4) or \
                               self.wait_for_element_clickable(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'login')]", timeout=4) or \
                               self.wait_for_element_clickable(By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'zaloguj')]", timeout=4) or \
                               self.wait_for_element_clickable(By.CSS_SELECTOR, "button.btn-primary", timeout=4)
                
                if not login_button:
                    logger.debug("未找到明确的登录按钮，尝试提交表单 (回车)")
                    try:
                        password_field.send_keys("\n")
                    except Exception:
                        logger.debug("回车提交失败")
                else:
                    logger.info("🖱️ 点击登录按钮...")
                    if not self.safe_click(login_button):
                        self.take_screenshot(f"error_click_failed_{name}")
                        return False, "登录按钮点击失败"
                
                # 等待登录结果
                time.sleep(5)
                
                # 检查登录是否成功（查看 URL / title / page source）
                current_url = self.driver.current_url or ''
                page_title = (self.driver.title or '').lower()
                page_source = (self.driver.page_source or '').lower()
                
                success_indicators = ['dashboard', 'panel', 'account', 'welcome', 'strona główna', 'logged', 'profile']
                error_indicators = ['error', 'błąd', 'invalid', 'nieprawidłowy', 'failed', 'unauthorized', 'forbidden']
                
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
                
                # 如果到这里，可能页面跳转但没有明显标志，返回“未知但可能成功”
                logger.info(f"⚠️ {name} 登录状态未知，但在 {url} 已尝试提交，当前 URL: {current_url}")
                self.take_screenshot(f"unknown_{name}")
                return True, "页面跳转完成"
                
            except Exception as e:
                logger.error(f"❌ 在尝试 {url} 登录时出现异常: {e}")
                # 继续尝试下一个候选 URL
                continue
        
        # 尝试所有候选 URL 都失败
        logger.error(f"❌ 所有候选登录页都尝试失败: {panel}")
        self.take_screenshot(f"error_all_candidates_{name}")
        return False, "无法找到合适的登录页面或登录失败"
    
    def process_all_accounts(self):
        """处理所有账号"""
        # 从环境变量获取账号信息
        accounts_json = os.environ.get('ACCOUNTS_JSON', '[]')
        logger.info("📦 读取 ACCOUNTS_JSON（已屏蔽密码）")
        logger.debug(f"原始 ACCOUNTS_JSON: {accounts_json}")
        
        try:
            accounts = json.loads(accounts_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ 账号JSON格式错误: {e}")
            return False
        
        if not accounts:
            logger.error("❌ 未找到账号配置")
            return False
        
        # 打印账号数量与用户名列表（不打印密码）
        try:
            usernames = [a.get('username') or a.get('user') or '' for a in accounts]
            logger.info(f"📋 找到 {len(accounts)} 个账号需要处理, 用户名列表: {usernames}")
        except Exception:
            logger.info(f"📋 找到 {len(accounts)} 个账号需要处理")
        
        # 设置浏览器
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
                    'message': message
                })
                
                # 间隔等待
                if i < len(accounts):
                    wait_time = 5
                    logger.info(f"⏳ 等待 {wait_time} 秒后处理下一个账号...")
                    time.sleep(wait_time)
            
            # 汇总结果
            success_count = sum(1 for r in results if r['success'])
            total_count = len(results)
            
            summary = f"🎯 Serv00 登录任务完成\n\n"
            summary += f"✅ 成功: {success_count}/{total_count}\n"
            summary += f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n\n"
            
            for result in results:
                status_icon = "✅" if result['success'] else "❌"
                summary += f"{status_icon} {result['name']}: {result['message']}\n"
            
            logger.info(summary)
            
            # 发送Telegram通知
            self.send_telegram_message(summary)
            
            return success_count > 0
            
        except Exception as e:
            logger.error(f"❌ 处理过程中出现异常: {e}")
            self.send_telegram_message(f"❌ Serv00 登录任务失败\n\n错误: {e}")
            return False
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception:
                    pass
                logger.info("🚪 浏览器已关闭")

def main():
    """主函数"""
    logger.info("🚀 开始执行 Serv00 自动登录脚本")
    
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