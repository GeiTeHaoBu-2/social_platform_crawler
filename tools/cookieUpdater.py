# 思路：
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import json
import time
import os
import requests

class CookieUpdater:
    """通用Cookie更新器：支持提取、缓存、检测、更新Cookie"""
    def __init__(self, chrome_data_dir: str, cookie_cache_file: str = "cookie_cache.json"):
        """
        初始化Cookie更新器
        :param chrome_data_dir: Chrome用户数据目录（复用配置的路径）
        :param cookie_cache_file: Cookie缓存文件路径（默认当前目录）
        """
        self.chrome_data_dir = chrome_data_dir
        self.cookie_cache_file = cookie_cache_file
        # Chrome通用配置（反反爬）
        self.chrome_options = self._get_chrome_options()

    def _get_chrome_options(self) -> webdriver.ChromeOptions:
        """生成Chrome配置（固定反反爬策略）"""
        options = webdriver.ChromeOptions()
        options.add_argument(f'--user-data-dir={self.chrome_data_dir}')
        options.add_argument('--profile-directory=Default')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return options

    def extract_cookie(self, target_url: str ) -> tuple[dict, str]:
        """
        提取目标网站的Cookie（通用方法）
        :param target_url: 目标网站URL（需已登录）
        :return: (cookie字典, cookie字符串)
        """
        try:
            print(f"🔄 启动Chrome提取[{target_url}]的Cookie...")
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=self.chrome_options
            )
            # 隐藏webdriver标识
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            driver.get(target_url)
            time.sleep(3)  # 等待页面加载完成

            # 提取Cookie并转换格式
            cookie_list = driver.get_cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookie_list}
            cookie_str = '; '.join([f"{k}={v}" for k, v in cookie_dict.items()])

            # 缓存到本地文件
            cache_data = {
                "cookie_dict": cookie_dict,
                "cookie_str": cookie_str,
                "update_time": time.time(),
                "target_url": target_url
            }
            with open(self.cookie_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            driver.quit()
            print(f"✅ Cookie提取并缓存至[{self.cookie_cache_file}]成功！")
            return cookie_dict, cookie_str

        except Exception as e:
            print(f"❌ 提取Cookie失败：{e}")
            raise  # 抛出异常，让调用方处理

    def load_cookie(self, expire_days: int = 7) -> tuple[dict, str]:
        """
        加载本地缓存的Cookie（优先复用）
        :param expire_days: Cookie过期天数（默认7天）
        :return: (cookie字典, cookie字符串)
        """
        if not os.path.exists(self.cookie_cache_file):
            raise FileNotFoundError(f"❌ 未找到Cookie缓存文件：{self.cookie_cache_file}")

        with open(self.cookie_cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)

        # 检查是否过期
        time_diff = time.time() - cache_data['update_time']
        if time_diff > expire_days * 24 * 3600:
            raise TimeoutError(f"❌ Cookie已过期（超过{expire_days}天），需重新提取")

        print("📌 加载本地缓存的Cookie（未过期）")
        return cache_data['cookie_dict'], cache_data['cookie_str']

    def check_cookie_valid(self, cookie_str: str, test_url: str, verify_func: callable) -> bool:
        """
        通用Cookie有效性检测
        :param cookie_str: Cookie字符串
        :param test_url: 测试URL（目标网站的接口/页面）
        :param verify_func: 验证函数（传入response，返回bool）
        :return: Cookie是否有效
        """
        try:
            headers = {"Cookie": cookie_str, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
            response = requests.get(test_url, headers=headers, timeout=5)
            return verify_func(response)
        except Exception as e:
            print(f"❌ 检测Cookie有效性失败：{e}")
            return False

    def get_valid_cookie(self, target_url: str, test_url: str, verify_func: callable, expire_days: int = 7) -> tuple[dict, str]:
        """
        一键获取有效Cookie（优先加载缓存，失效则重新提取）
        :param target_url: 提取Cookie的目标网站URL
        :param test_url: 检测Cookie的测试URL
        :param verify_func: 验证函数
        :param expire_days: 过期天数
        :return: (cookie字典, cookie字符串)
        """
        try:
            # 第一步：尝试加载缓存Cookie
            cookie_dict, cookie_str = self.load_cookie(expire_days)
            # 第二步：检测Cookie是否有效
            if self.check_cookie_valid(cookie_str, test_url, verify_func):
                return cookie_dict, cookie_str
            else:
                print("⚠️  缓存Cookie无效，重新提取...")
                return self.extract_cookie(target_url)
        except (FileNotFoundError, TimeoutError):
            # 缓存不存在/过期，直接提取
            return self.extract_cookie(target_url)