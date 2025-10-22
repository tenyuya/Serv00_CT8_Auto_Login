import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, ElementNotInteractableException, NoSuchElementException
import datetime
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("serv00_login.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class Serv00AutoLogin:
    def __init__(self):
        self.driver = None
        self.wait = None
        
    def setup_driver(self):
        """设置浏览器驱动"""
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 如果需要无头模式，取消下面的注释
        # options.add_argument('--headless')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 15)
            logger.info("浏览器驱动设置完成")
            return True
        except Exception as e:
            logger.error(f"浏览器驱动设置失败: {e}")
            return False
        
    def wait_for_element_clickable(self, by, value, timeout=10):
        """等待元素可点击"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            logger.error(f"元素不可点击: {by}={value}")
            return None
        
    def wait_for_element_visible(self, by, value, timeout=10):
        """等待元素可见"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, value))
            )
        except TimeoutException:
            logger.error(f"元素不可见: {by}={value}")
            return None
        
    def safe_click(self, element):
        """安全的点击方法"""
        try:
            # 方法1: 直接点击
            element.click()
            logger.info("直接点击成功")
            return True
        except ElementNotInteractableException:
            try:
                # 方法2: 使用JavaScript点击
                self.driver.execute_script("arguments[0].click();", element)
                logger.info("JavaScript点击成功")
                return True
            except Exception as e:
                logger.error(f"JavaScript点击失败: {e}")
                return False
        except Exception as e:
            logger.error(f"点击失败: {e}")
            return False
                
    def scroll_to_element(self, element):
        """滚动到元素位置"""
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
        time.sleep(0.5)
        
    def force_input(self, element, text):
        """强制输入文本"""
        try:
            element.clear()
            element.send_keys(text)
        except:
            self.driver.execute_script(f"arguments[0].value = '{text}';", element)
            # 触发输入事件
            self.driver.execute_script("""
                var event = new Event('input', { bubbles: true });
                arguments[0].dispatchEvent(event);
            """, element)
        
    def check_for_overlays(self):
        """检查是否有遮挡层"""
        overlay_selectors = [
            '.modal',
            '.popup', 
            '.overlay',
            '[class*="modal"]',
            '[class*="popup"]',
            '[class*="overlay"]',
            '.loading',
            '.spinner'
        ]
        
        for selector in overlay_selectors:
            try:
                overlays = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for overlay in overlays:
                    # 检查遮挡层是否可见
                    if overlay.is_displayed():
                        logger.warning(f"发现遮挡层: {selector}")
                        # 尝试关闭遮挡层
                        self.driver.execute_script("arguments[0].style.display = 'none';", overlay)
            except:
                continue
                
    def take_screenshot(self, filename):
        """截取屏幕截图"""
        try:
            screenshot_dir = "screenshots"
            if not os.path.exists(screenshot_dir):
                os.makedirs(screenshot_dir)
                
            filepath = os.path.join(screenshot_dir, filename)
            self.driver.save_screenshot(filepath)
            logger.info(f"截图已保存: {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"截图失败: {e}")
            return None
            
    def get_utc_time(self):
        """获取UTC时间"""
        return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        
    def login_to_serv00(self, url, username, password, account_name):
        """登录Serv00的主方法"""
        logger.info(f"🌐 UTC时间: {self.get_utc_time()}")
        logger.info(f"正在访问: {url}")
        
        try:
            # 访问页面
            self.driver.get(url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 检查并处理可能的遮挡层
            self.check_for_overlays()
            
            # 定位用户名输入框
            logger.info("正在定位用户名输入框...")
            username_selectors = [
                "input[name='login']",
                "input[name='username']", 
                "input[type='text']",
                "input[placeholder*='login']",
                "input[placeholder*='user']",
                "#username",
                "#login"
            ]
            
            username_field = None
            for selector in username_selectors:
                try:
                    username_field = self.wait_for_element_visible(By.CSS_SELECTOR, selector, 5)
                    if username_field:
                        logger.info(f"找到用户名输入框，使用选择器: {selector}")
                        break
                except:
                    continue
                    
            if not username_field:
                # 尝试通过XPath查找
                xpath_selectors = [
                    "//input[contains(@placeholder, 'Login')]",
                    "//input[contains(@placeholder, 'login')]",
                    "//input[contains(@placeholder, 'User')]",
                    "//input[contains(@placeholder, 'user')]"
                ]
                
                for xpath in xpath_selectors:
                    try:
                        username_field = self.wait_for_element_visible(By.XPATH, xpath, 3)
                        if username_field:
                            logger.info(f"找到用户名输入框，使用XPath: {xpath}")
                            break
                    except:
                        continue
                    
            if not username_field:
                error_msg = "未找到用户名输入框"
                logger.error(error_msg)
                self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
                return False, error_msg
                
            # 输入用户名
            logger.info("开始输入用户名...")
            self.scroll_to_element(username_field)
            self.force_input(username_field, username)
            logger.info("用户名输入完成")
            
            # 定位密码输入框
            logger.info("正在定位密码输入框...")
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[placeholder*='password']",
                "input[placeholder*='hasło']",
                "#password",
                "#pass"
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.wait_for_element_visible(By.CSS_SELECTOR, selector, 5)
                    if password_field:
                        logger.info(f"找到密码输入框，使用选择器: {selector}")
                        break
                except:
                    continue
                    
            if not password_field:
                # 尝试通过XPath查找
                xpath_selectors = [
                    "//input[contains(@placeholder, 'Password')]",
                    "//input[contains(@placeholder, 'password')]",
                    "//input[contains(@placeholder, 'Hasło')]",
                    "//input[contains(@placeholder, 'hasło')]"
                ]
                
                for xpath in xpath_selectors:
                    try:
                        password_field = self.wait_for_element_visible(By.XPATH, xpath, 3)
                        if password_field:
                            logger.info(f"找到密码输入框，使用XPath: {xpath}")
                            break
                    except:
                        continue
                    
            if not password_field:
                error_msg = "未找到密码输入框"
                logger.error(error_msg)
                self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
                return False, error_msg
                
            # 输入密码
            logger.info("开始输入密码...")
            self.scroll_to_element(password_field)
            self.force_input(password_field, password)
            logger.info("密码输入完成")
            
            # 等待一下让表单验证完成
            time.sleep(1)
            
            # 定位登录按钮
            logger.info("正在定位登录按钮...")
            button_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:contains('Zaloguj')",
                "input[value*='Zaloguj']",
                "button:contains('Login')",
                "input[value*='Login']",
                "button.btn",
                "input.btn",
                ".login-btn",
                "#login-btn"
            ]
            
            login_button = None
            for selector in button_selectors:
                try:
                    if "contains" in selector:
                        # 处理文本包含的选择器
                        text = selector.split("contains('")[1].split("')")[0]
                        xpath = f"//*[contains(text(), '{text}')]"
                        login_button = self.wait_for_element_visible(By.XPATH, xpath, 3)
                    else:
                        login_button = self.wait_for_element_visible(By.CSS_SELECTOR, selector, 3)
                    
                    if login_button:
                        logger.info(f"找到登录按钮，使用选择器: {selector}")
                        break
                except:
                    continue
                    
            if not login_button:
                # 尝试通过按钮文本查找
                button_texts = ['Zaloguj się', 'Zaloguj', 'Login', 'Sign in']
                for text in button_texts:
                    try:
                        xpath = f"//button[contains(text(), '{text}')]"
                        login_button = self.wait_for_element_visible(By.XPATH, xpath, 3)
                        if login_button:
                            logger.info(f"找到登录按钮，使用文本: {text}")
                            break
                    except:
                        continue
                    
            if not login_button:
                error_msg = "未找到登录按钮"
                logger.error(error_msg)
                self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
                return False, error_msg
                
            # 滚动到按钮位置
            logger.info("滚动到登录按钮...")
            self.scroll_to_element(login_button)
            time.sleep(1)
            
            # 再次检查遮挡层
            self.check_for_overlays()
            
            # 检查按钮状态
            button_state = self.driver.execute_script("""
                var elem = arguments[0];
                return {
                    display: window.getComputedStyle(elem).display,
                    visibility: window.getComputedStyle(elem).visibility,
                    opacity: window.getComputedStyle(elem).opacity,
                    disabled: elem.disabled,
                    readonly: elem.readOnly,
                    visible: elem.offsetWidth > 0 && elem.offsetHeight > 0
                }
            """, login_button)
            
            logger.info(f"按钮状态: {button_state}")
            
            # 如果按钮被禁用，尝试启用它
            if button_state.get('disabled', False):
                self.driver.execute_script("arguments[0].disabled = false;", login_button)
                logger.info("已启用被禁用的按钮")
            
            # 点击登录按钮
            logger.info("准备点击登录按钮...")
            if self.safe_click(login_button):
                logger.info("登录按钮点击成功")
                
                # 等待登录结果
                time.sleep(5)
                
                # 检查登录是否成功
                current_url = self.driver.current_url
                if "dashboard" in current_url.lower() or "panel" in current_url.lower() or "account" in current_url.lower():
                    logger.info(f"{account_name} 登录成功!")
                    self.take_screenshot(f"success_{account_name}_{int(time.time())}.png")
                    return True, "登录成功"
                else:
                    # 检查是否有错误消息
                    error_selectors = ['.error', '.alert-danger', '.text-danger', '[class*="error"]']
                    error_msg = "未知错误"
                    for selector in error_selectors:
                        try:
                            errors = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            for error in errors:
                                if error.is_displayed():
                                    error_text = error.text.strip()
                                    if error_text:
                                        error_msg = error_text
                                        logger.error(f"登录错误: {error_text}")
                                        break
                        except:
                            continue
                    
                    self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
                    return False, error_msg
            else:
                error_msg = "登录按钮点击失败"
                logger.error(error_msg)
                self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
                return False, error_msg
                
        except Exception as e:
            error_msg = f"登录过程中出现异常: {str(e)}"
            logger.error(error_msg)
            self.take_screenshot(f"error_{account_name}_{int(time.time())}.png")
            return False, error_msg
            
    def process_accounts(self, accounts):
        """处理所有账号"""
        if not self.setup_driver():
            logger.error("无法启动浏览器，程序退出")
            return False
            
        results = []
        
        try:
            for i, account in enumerate(accounts, 1):
                logger.info(f"正在处理第 {i}/{len(accounts)} 个账号: {account['name']}")
                
                success, message = self.login_to_serv00(
                    account['url'], 
                    account['username'], 
                    account['password'], 
                    account['name']
                )
                
                results.append({
                    'account': account['name'],
                    'success': success,
                    'message': message
                })
                
                if success:
                    logger.info(f"{account['name']} 处理完成")
                else:
                    logger.error(f"{account['name']} 处理失败: {message}")
                
                # 如果不是最后一个账号，等待一段时间
                if i < len(accounts):
                    wait_time = 5
                    logger.info(f"等待 {wait_time} 秒后处理下一个账号...")
                    time.sleep(wait_time)
                    
            # 汇总结果
            success_count = sum(1 for r in results if r['success'])
            logger.info(f"所有账号登录完成！成功: {success_count}/{len(accounts)}")
            
            # 发送通知（这里可以集成Telegram等通知服务）
            self.send_notification(results)
            
            return True
                    
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("浏览器已关闭")
                
    def send_notification(self, results):
        """发送通知（需要自行实现）"""
        # 这里可以集成Telegram、邮件等通知服务
        success_count = sum(1 for r in results if r['success'])
        total_count = len(results)
        
        message = f"Serv00登录完成\n成功: {success_count}/{total_count}\n时间: {self.get_utc_time()}"
        
        for result in results:
            status = "✅" if result['success'] else "❌"
            message += f"\n{status} {result['account']}: {result['message']}"
        
        logger.info(f"通知消息: {message}")
        
        # 示例：Telegram通知（需要安装python-telegram-bot）
        # try:
        #     import telegram
        #     bot = telegram.Bot(token='YOUR_TELEGRAM_BOT_TOKEN')
        #     bot.send_message(chat_id='YOUR_CHAT_ID', text=message)
        #     logger.info("Telegram消息发送成功")
        # except ImportError:
        #     logger.warning("未安装python-telegram-bot库，无法发送Telegram通知")
        # except Exception as e:
        #     logger.error(f"Telegram通知发送
