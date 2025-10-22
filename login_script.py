import os
import json
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
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
        headless_env = os.environ.get('HEADLESS', 'true').lower()
        self.headless = headless_env in ['1', 'true', 'yes']

    def setup_driver(self):
        """设置浏览器驱动"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        if self.headless:
            chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            try:
                self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                    "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
                })
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
            candidates.append(panel_value)
            candidates.append('https://' + panel_value)
            candidates.append('http://' + panel_value)
            candidates.append('https://' + panel_value + '/login')
            candidates.append('https://' + panel_value + '/admin/login')
            candidates.append('http://' + panel_value + '/login')
            candidates.append('http://' + panel_value + '/admin/login')
        seen = set()
        return [u for u in candidates if not (u in seen or seen.add(u))]

    def login_to_serv00(self, account_info):
        name = account_info.get('name') or account_info.get('username') or account_info.get('panel') or '未知账号'
        panel = account_info.get('panel') or account_info.get('url') or account_info.get('host') or ''
        username = account_info.get('username') or account_info.get('user') or ''
        password = account_info.get('password') or account_info.get('pass') or ''

        if not panel or not username or not password:
            logger.error(f"❌ 账号信息不完整: {name}")
            return False, "账号信息不完整"

        logger.info(f"🔐 开始处理账号: