from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
import re

# 1. 配置Chrome浏览器（无头模式：不显示浏览器窗口，注释掉则显示）
options = webdriver.ChromeOptions()
options.add_argument('--headless=new')  # 无头模式，可选
options.add_argument('--disable-blink-features=AutomationControlled')  # 规避selenium被检测
options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
options.add_experimental_option("excludeSwitches", ["enable-automation"])
options.add_experimental_option('useAutomationExtension', False)
print('配置完成')

# 2. 启动浏览器，访问微博实时热搜页（正确URL）
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
# 微博实时热搜正确地址（无需登录即可访问基础热搜）
#url = 'https://s.weibo.com/top/summary?cate=realtimehot'
url = 'https://weibo.com/hot/search'
driver.get(url)
time.sleep(3)  # 等待页面加载完成（关键：微博加载慢，需留足够时间）
print('启动成功')

# 3. 获取页面源码，解析热搜
page_source = driver.page_source
soup = BeautifulSoup(page_source, 'lxml')
hot_container = soup.find('div', id='pl_top_realtimehot')  # 核心容器：仅包含真实热搜榜
if not hot_container:
    print("未找到热搜核心容器，可能Cookie/反爬拦截")
    driver.quit()
    exit()
print('解析成功')


# 4. 定位热搜标题（微博热搜的标签/class可能会变，需核对）
# 核心：通过开发者工具（F12）确认热搜条目对应的标签
hot_list = hot_container.find_all('a', href=re.compile(r'^/weibo\?q='), target='_blank')
print('定位成功')


# 5. 正则：保留中文+数字+字母+%（核心修改）
pattern = re.compile(r'[\u4e00-\u9fa50-9a-zA-Z%":]+')

print("置顶热搜："+hot_list[0].get_text())
# 6. 提取并打印热搜
for idx, link in enumerate(hot_list, 1):
    if idx == 1:
        continue  # 跳过第一条热搜，但是每次都要判断，待优化
    raw_title = link.get_text(strip=True)  # 提取纯文本，去除首尾空格
    #result_title = ''.join(pattern.findall(raw_title))  # 拼接匹配的字符
    print(f'第{idx-1}条热搜：{raw_title}')

# 6. 关闭浏览器
driver.quit()
