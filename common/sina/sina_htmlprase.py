import requests
from bs4 import BeautifulSoup
import time
import os
import sys

# 将工程根目录加入模块搜索路径，以便 import common.rdata.redis_client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# 从 rdata.redis_client 导入保存函数
from common.rdata.redis_client import save_hot_search_to_redis

url = "https://s.weibo.com/top/summary"

# 请求头（需替换为自己的Cookie，从浏览器F12抓包获取）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": "PC_TOKEN=c6d5692d12; ALF=02_1769593751; SCF=Ajn0diikk2WYz_4OlN61z6NE471qVTDPHB3-9ylg7mOGIR4O1WbygPxIAm046YdPKXBE2vCjse4uEwNu1GecQF4.; SUB=_2A25EVj7HDeRhGeFJ41oU-CvMzDuIHXVnKj4PrDV8PUJbkNB-LUr8kW1NfvAsCpo7_SrJp5WWLR6tguqkNVoCz2kP; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WFm2BdFQxr7PVATg3GWDoyy5NHD95QNS0nRSKnfehMNWs4Dqc_ei--ciK.fi-z7i--Ri-88i-2pi--4iK.4i-2Ei--Xi-isi-2pi--Ni-88i-2peKzEeEH8SC-4eFHFSFH8SEHFBCHWBCH81FHFxCHFe5tt; _s_tentry=-; Apache=5943957075602.887.1767002130326; SINAGLOBAL=5943957075602.887.1767002130326; ULV=1767002130330:1:1:1:5943957075602.887.1767002130326:",
    "Referer": "https://weibo.com/",
    "X-Requested-With": "XMLHttpRequest"
}

try:
    # 在requests.get()中添加proxies参数
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()  # 如果状态码不是200，则抛出异常
    response.encoding = response.apparent_encoding  # 自动判断编码，避免乱码
    print("请求成功！")
except requests.exceptions.RequestException as e:
    print(f"请求失败：{e}")
    exit()

soup = BeautifulSoup(response.text, 'lxml')
# 通过检查元素，发现热搜列表在一个id为`pl_top_realtimehot`的table下的tbody中
# 我们首先找到这个table
hot_search_table = soup.find('tbody')
if hot_search_table is None:
    print("未找到热搜列表表格，请检查页面结构或Cookie是否有效")
    exit()

# 然后找到表格内的所有tr标签
items = hot_search_table.find_all('tr')

hot_searches = []  # 用于存储所有热搜字典的列表

# 遍历每一个tr标签（跳过第一个表头tr）
for index, tr in enumerate(items[1:], start=1): # 从1开始计数，作为排名
    # 提取热搜标题，通常在<td class="td-02">下的<a>标签里
    title_tag = tr.find('td', class_='td-02').find('a')
    if not title_tag:
        continue

    title = title_tag.get_text(strip=True)

    # 简单清洗 title（可选）
    clean_title = " ".join(title.split())

    # 提取链接
    if title_tag.get('href') == 'javascript:void(0);':
        link = "https://s.weibo.com" + title_tag.get('href_to')
    else:
        link = "https://s.weibo.com" + title_tag['href'] if title_tag.get('href') else None

    # 提取搜索量，可能在<span>标签里
    span_tag = tr.find('td', class_='td-02').find('span')
    hot_count = span_tag.get_text(strip=True) if span_tag else "未知"

    # 提取标签，比如`新`、`热`、`爆`，可能在<a>标签下的<i>标签里
    i_tag = tr.find('td', class_='td-03').find('i')
    tag = i_tag.get_text(strip=True) if i_tag else ""

    # 构建一个字典来存储一条热搜信息
    hot_search_item = {
        'rank': index,
        'title': clean_title,
        'url': link,
        'hot_count': hot_count,
        'tag': tag,
        'first_crawled': time.time()
    }

    hot_searches.append(hot_search_item)

    # 打印单条结果（可选）
    print(f"{index}. {title} [{tag}] (热度: {hot_count}) - {link}")

    # 新增：调用 Redis 存储函数保存热搜
    try:
        save_hot_search_to_redis(hot_search_item)
    except Exception as e:
        print(f"保存到 Redis 失败: {e}")
