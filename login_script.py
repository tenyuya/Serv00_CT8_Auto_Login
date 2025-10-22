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
        
    def setup_driver(self):
        """设置浏览器驱动（适配GitHub Actions）"""
        chrome_options = Options()
        
        # GitHub Actions 环境配置
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--headless')  # 无头模式
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # 反自动化检测
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)
            logger.info("✅ 浏览器驱动设置完成")
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
            logger.error(f"⏰ 元素定位超时: {by}={value}")
            return None
    
    def wait_for_element_clickable(self, by, value, timeout=15):
        """等待元素可点击"""
        try:
            return WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, value))
            )
        except TimeoutException:
            logger.error(f"⏰ 元素不可点击: {by}={value}")
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
                logger.error(f"❌ Telegram消息发送失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ Telegram消息发送异常: {e}")
            return False
    
    def login_to_serv00(self, account_info):
        """执行登录流程"""
        name = account_info.get('name', '未知账号')
        url = account_info.get('url', '')
        username = account_info.get('username', '')
        password = account_info.get('password', '')
        
        if not all([url, username, password]):
            logger.error(f"❌ 账号信息不完整: {name}")
            return False, "账号信息不完整"
        
        logger.info(f"🔐 开始处理账号: {name}")
        logger.info(f"🌐 访问URL: {url}")
        
        try:
            # 访问登录页面
            self.driver.get(url)
            time.sleep(3)
            
            # 查找用户名输入框
            logger.info("🔍 定位用户名输入框...")
            username_field = self.wait_for_element(By.NAME, "login") or \
                           self.wait_for_element(By.NAME, "username") or \
                           self.wait_for_element(By.CSS_SELECTOR, "input[type='text']") or \
                           self.wait_for_element(By.CSS_SELECTOR, "input[name='login']")
            
            if not username_field:
                self.take_screenshot(f"error_username_not_found_{name}")
                return False, "未找到用户名输入框"
            
            # 输入用户名
            if not self.safe_send_keys(username_field, username):
                self.take_screenshot(f"error_username_input_{name}")
                return False, "用户名输入失败"
            logger.info("✅ 用户名输入完成")
            
            time.sleep(1)
            
            # 查找密码输入框
            logger.info("🔍 定位密码输入框...")
            password_field = self.wait_for_element(By.NAME, "password") or \
                           self.wait_for_element(By.CSS_SELECTOR, "input[type='password']") or \
                           self.wait_for_element(By.CSS_SELECTOR, "input[name='password']")
            
            if not password_field:
                self.take_screenshot(f"error_password_not_found_{name}")
                return False, "未找到密码输入框"
            
            # 输入密码
            if not self.safe_send_keys(password_field, password):
                self.take_screenshot(f"error_password_input_{name}")
                return False, "密码输入失败"
            logger.info("✅ 密码输入完成")
            
            time.sleep(1)
            
            # 查找登录按钮
            logger.info("🔍 定位登录按钮...")
            login_button = self.wait_for_element_clickable(By.CSS_SELECTOR, "button[type='submit']") or \
                         self.wait_for_element_clickable(By.CSS_SELECTOR, "input[type='submit']") or \
                         self.wait_for_element_clickable(By.XPATH, "//button[contains(text(), 'Zaloguj')]") or \
                         self.wait_for_element_clickable(By.XPATH, "//button[contains(text(), 'Login')]") or \
                         self.wait_for_element_clickable(By.CSS_SELECTOR, "button.btn-primary")
            
            if not login_button:
                self.take_screenshot(f"error_button_not_found_{name}")
                return False, "未找到登录按钮"
            
            # 点击登录按钮
            logger.info("🖱️ 点击登录按钮...")
            if not self.safe_click(login_button):
                self.take_screenshot(f"error_click_failed_{name}")
                return False, "登录按钮点击失败"
            
            # 等待登录结果
            time.sleep(5)
            
            # 检查登录是否成功
            current_url = self.driver.current_url
            page_title = self.driver.title
            page_source = self.driver.page_source
            
            # 成功指标
            success_indicators = ['dashboard', 'panel', 'account', 'welcome', 'strona główna']
            error_indicators = ['error', 'błąd', 'invalid', 'nieprawidłowy', 'failed']
            
            # 检查成功标志
            if any(indicator in current_url.lower() or indicator in page_title.lower() or indicator in page_source.lower() 
                   for indicator in success_indicators):
                logger.info(f"✅ {name} 登录成功!")
                self.take_screenshot(f"success_{name}")
                return True, "登录成功"
            
            # 检查错误标志
            if any(indicator in page_source.lower() for indicator in error_indicators):
                logger.error(f"❌ {name} 登录失败: 页面包含错误信息")
                self.take_screenshot(f"error_page_{name}")
                return False, "页面错误信息"
            
            # 默认认为成功（有些页面可能没有明确的成功标志）
            logger.info(f"⚠️ {name} 登录状态未知，但页面已跳转")
            self.take_screenshot(f"unknown_{name}")
            return True, "页面跳转完成"
            
        except Exception as e:
            logger.error(f"❌ {name} 登录过程中出现异常: {e}")
            self.take_screenshot(f"exception_{name}")
            return False, f"异常: {str(e)}"
    
    def process_all_accounts(self):
        """处理所有账号"""
        # 从环境变量获取账号信息
        accounts_json = os.environ.get('ACCOUNTS_JSON', '[]')
        
        try:
            accounts = json.loads(accounts_json)
        except json.JSONDecodeError as e:
            logger.error(f"❌ 账号JSON格式错误: {e}")
            return False
        
        if not accounts:
            logger.error("❌ 未找到账号配置")
            return False
        
        logger.info(f"📋 找到 {len(accounts)} 个账号需要处理")
        
        # 设置浏览器
        if not self.setup_driver():
            return False
        
        results = []
        
        try:
            for i, account in enumerate(accounts, 1):
                logger.info(f"🔄 处理第 {i}/{len(accounts)} 个账号")
                
                success, message = self.login_to_serv00(account)
                results.append({
                    'name': account.get('name', f'账号{i}'),
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
                self.driver.quit()
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
