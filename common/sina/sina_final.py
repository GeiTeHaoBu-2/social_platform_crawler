import requests
import time
import random
from tools.cookieUpdater import get_cookie

# 微博热搜核心接口（抓包确认的最新接口）
HOT_SEARCH_URL = "https://weibo.com/ajax/side/hotSearch.json"
cookie = cookie_str

# requests 请求头（需和抓包一致）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://weibo.com/",
    "X-Requested-With": "XMLHttpRequest",
    "Cookie": cookie_str  # 用 Selenium 提取的 Cookie 字符串
}

# 高频爬取函数（示例：每分钟爬一次，持续10次）
def high_freq_crawl():
    for i in range(10):
        try:
            # 发送请求（添加随机延迟，避免风控）
            response = requests.get(HOT_SEARCH_URL, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                hot_list = data.get("rdata", {}).get("realtime_hot_list", [])
                print(f"\n=== 第 {i+1} 次爬取（{time.strftime('%H:%M:%S')}）===")
                for idx, hot in enumerate(hot_list[:10], 1):  # 取前10条
                    print(f"{idx}. {hot.get('note')}（热度：{hot.get('hot')}）")
            else:
                print(f"请求失败：状态码 {response.status_code}，Cookie 可能过期")
                # Cookie 过期时，重新提取 Cookie
                global cookie_str
                cookie_dict, cookie_str = get_cookie()
                headers["Cookie"] = cookie_str  # 更新 Cookie
        except Exception as e:
            print(f"爬取异常：{e}")

        # 控制频率（关键：避免高频触发反爬，建议 30秒~5分钟 一次）
        sleep_time = random.uniform(30, 60)  # 随机30~60秒
        print(f"等待 {sleep_time:.1f} 秒后继续...")
        time.sleep(sleep_time)

# 启动高频爬取
high_freq_crawl()