import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ===================== 关键配置 =====================
crawler_profile_path = r"D:\Chrome_Crawler_Profile"
api_save_file = "kuaishou_all_api.txt"
# 确保文件可写（清空旧文件）
if os.path.exists(api_save_file):
    os.remove(api_save_file)
    print(f"✅ 清空旧的API文件：{api_save_file}")

# ===================== 创建配置目录 =====================
if not os.path.exists(crawler_profile_path):
    os.makedirs(crawler_profile_path)
    print(f"✅ 已创建独立爬虫配置目录：{crawler_profile_path}")

# ===================== Chrome配置 =====================
options = webdriver.ChromeOptions()
options.add_argument(f'--user-rdata-dir={crawler_profile_path}')
options.add_argument('--profile-directory=Default')
# 关闭无头模式！必须前台运行，确保页面能正常加载
# options.add_argument('--headless=new')
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

# ===================== 启动Chrome + 启用CDP监听 =====================
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # 1. 启用CDP的Network监听（核心！替代get_log）
    driver.execute_cdp_cmd('Network.enable', {})
    # 2. 存储捕获的请求URL
    captured_urls = set()  # 去重

    # 3. 监听Network请求完成事件（最可靠的方式）
    def capture_request(request):
        """回调函数：捕获所有完成的请求URL"""
        try:
            url = request.get('params', {}).get('request', {}).get('url', '')
            if url and url not in captured_urls:
                captured_urls.add(url)
                # 实时打印候选URL（方便排查）
                print(f"📤 捕获请求：{url[:100]}...")  # 截断长URL
        except Exception as e:
            print(f"⚠️  捕获请求异常：{str(e)[:50]}")

    # 注册回调：监听requestFinished事件
    driver.add_event_listener('Network.requestFinished', capture_request)

    # 隐藏webdriver标识
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print("\n✅ 独立Chrome窗口已启动（CDP监听已开启）")
except Exception as e:
    print(f"\n❌ Chrome启动失败：{e}")
    exit()

# ===================== 访问页面 + 触发加载 =====================
# 优先用移动端热榜（反爬弱，API更简单）
driver.get("https://m.kuaishou.com/hot/rank?active=1")
print("✅ 已访问快手移动端热榜页，等待加载...")

try:
    # 等待页面完全加载 + 模拟滚动（触发更多请求）
    wait = WebDriverWait(driver, 20)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # 模拟滚动页面，确保所有热榜数据请求被触发
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(10)  # 延长等待，确保所有请求完成
    print("✅ 页面加载+滚动完成，开始保存API...")

    # ===================== 保存所有捕获的URL到文件 =====================
    with open(api_save_file, 'w', encoding='utf-8') as f:
        for url in sorted(captured_urls):
            # 过滤无效URL（只保留http/https）
            if url.startswith(('http://', 'https://')):
                f.write(f"{url}\n")

    # 验证文件是否为空
    file_size = os.path.getsize(api_save_file)
    if file_size == 0:
        print("❌ API文件为空！可能是页面未加载/被反爬拦截")
    else:
        print(f"✅ 共捕获{len(captured_urls)}个唯一请求，已保存到：{api_save_file}")
        print("👉 重点筛选包含以下关键词的URL：hot、rank、list、api、rdata、feed")

except Exception as e:
    print(f"\n❌ 爬取过程异常：{str(e)}")
finally:
    # 关闭CDP监听 + 退出浏览器
    driver.execute_cdp_cmd('Network.disable', {})
    driver.quit()
    print("\n✅ Chrome已关闭")