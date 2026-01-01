from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re
import time
import os

# 自定义一个空目录路径（建议放在非系统盘，比如D盘）
crawler_profile_path = r"D:\Chrome_Crawler_Profile"
# 自动创建该目录（如果不存在）
if not os.path.exists(crawler_profile_path):
    os.makedirs(crawler_profile_path)
    print(f"已创建独立爬虫配置目录：{crawler_profile_path}")

# 1. Chrome配置（核心：使用独立配置目录，隔离主Chrome）
options = webdriver.ChromeOptions()
# 指向独立配置目录（关键：不和主Chrome冲突）
options.add_argument(f'--user-data-dir={crawler_profile_path}')
options.add_argument('--profile-directory=Default')  # 该目录下的默认配置

# 反反爬配置（不影响主Chrome）
options.add_argument('--headless=new')  # 无头模式
options.add_argument('--disable-blink-features=AutomationControlled')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)

# 2. 启动Chrome（无需关闭主Chrome）
try:
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    print("\n✅ 独立Chrome窗口已启动（主Chrome可正常使用）")
except Exception as e:
    print(f"\n❌ Chrome启动失败：{e}")
    exit()

# 3. 访问知乎热搜（第一次运行需要手动登录）
url = 'https://www.zhihu.com/hot'
driver.get(url)
driver.maximize_window()# 窗口最大化

# 4. 等待热搜元素加载
wait = WebDriverWait(driver, 15)
try:
    wait.until(EC.presence_of_element_located((By.XPATH, '//h2[contains(@class, "HotItem-title")]')))
    print("✅ 知乎热搜页面加载成功")
except Exception as e:
    print(f"\n❌ 元素加载超时：{e}")
    print(f"当前页面URL：{driver.current_url}")
    driver.quit()
    exit()

# 5. 解析并打印热搜
page_source = driver.page_source
soup = BeautifulSoup(page_source, 'lxml')
hot_titles = soup.find_all('h2', class_=re.compile('HotItem-title'))
hot_titles2 = soup.find_all('a', herf=re.compile(''))

if hot_titles:
    print('='*60 + '\n📈 知乎实时热搜\n' + '='*60)
    pattern = re.compile(r'[\u4e00-\u9fa50-9a-zA-Z%":，。！？、]+')
    for idx, title_tag in enumerate(hot_titles, 1):
        raw_title = title_tag.get_text(strip=True)
        clean_title = ''.join(pattern.findall(raw_title))
        if clean_title:
            print(f'第{idx:2d}条：{clean_title}')
else:
    print("❌ 未找到热搜标题（可能页面结构更新）")

# 6. 关闭浏览器（Cookie已保存在独立配置目录，下次运行无需登录）
driver.quit()
print(f"\n✅ 爬取完成！Cookie已保存到：{crawler_profile_path}")
print("✅ 下次运行无需登录，且不影响主Chrome浏览器")