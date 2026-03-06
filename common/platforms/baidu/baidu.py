from bs4 import BeautifulSoup
import requests
import re  # 导入正则表达式库，用于筛选中文字符


# 指定你想要获取标题的网站
url = 'https://top.baidu.com/board?tab=realtime'

# 发送HTTP请求获取网页内容
response = requests.get(url)
# 中文乱码问题
response.encoding = 'utf-8'

soup = BeautifulSoup(response.text, 'lxml')


# 查找所有 <a> 标签
all_links = soup.find_all('div', class_='c-single-text-ellipsis')
# 定义正则表达式：匹配所有中文字符（\u4e00-\u9fa5是中文Unicode范围）
chinese_pattern = re.compile(r'[\u4e00-\u9fa5]+')

for link in all_links:
    # 1. 提取标签内的纯文本，并去除首尾空格
    raw_text = link.get_text(strip=True)
    # 2. 筛选出所有中文字符，拼接成完整字符串
    chinese_text = ''.join(chinese_pattern.findall(raw_text))
    # 3. 打印结果（过滤空字符串）
    if chinese_text:
        print(chinese_text)