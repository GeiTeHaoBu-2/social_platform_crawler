import requests
from bs4 import BeautifulSoup
import time
import os
import sys
import re  # 引入正则模块

from common.config.settings import WEIBO_HEADERS, WEIBO_URL
from common.models.item import HotSearchItem
from common.utils.logging_config import logger

# 将工程根目录加入模块搜索路径，以便 import common.storage.redis_client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
# 导入settings
url = WEIBO_URL
headers = WEIBO_HEADERS

def get_realtime_data() -> list[HotSearchItem]:
    """
        爬取微博热搜，并返回标准化 HotSearchItem 对象列表。
        这里只做数据搬运和基础对象封装，绝不涉及数据库操作。
    """
    # 发送HTTP请求获取页面内容
    try:
        # 在requests.get()中添加proxies参数
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 如果状态码不是200，则抛出异常
        response.encoding = response.apparent_encoding  # 自动判断编码，避免乱码
        logger.info("请求成功！")
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败：{e}")
        exit()

    # 解析HTML内容
    soup = BeautifulSoup(response.text, 'lxml')
    # 通过检查元素，发现热搜列表在一个id为`pl_top_realtimehot`的table下的tbody中
    # 我们首先找到这个table
    hot_search_table = soup.find('tbody')
    if hot_search_table is None:
        logger.error("未找到热搜列表表格，请检查页面结构或Cookie是否有效")
        exit()

    # 然后找到表格内的所有tr标签
    items = hot_search_table.find_all('tr')
    hot_searches = []  # 用于存储所有热搜字典的列表

    # 获取当次抓取的统一时间戳
    current_timestamp = int(time.time())

    # 遍历每一个tr标签（跳过第一个表头tr，因为是置顶新闻）
    for index, tr in enumerate(items[1:], start=1):

        rank_td = tr.find('td', class_='td-01')
        rank_text = rank_td.get_text(strip=True)
        if not rank_text.isdigit():
            logger.info("跳过广告或置顶条目（排名非纯数字）")
            continue

        # 提取热度，并安全转换为 int
        span_tag = tr.find('td', class_='td-02').find('span')
        hot_count_str = span_tag.get_text(strip=True) if span_tag else "0"
        # 使用正则表达式提取连续的数字 \d+ 表示匹配一个或多个连续的数字（0-9）
        match = re.search(r'\d+', hot_count_str)
        if match:
            heat_val = int(match.group())            # group() 会返回匹配到的纯数字字符串，例如 '309392'
        else:
            heat_val = 0

        # 提取热搜标题，通常在<td class="td-02">下的<a>标签里
        title_tag = tr.find('td', class_='td-02').find('a')
        title = title_tag.get_text(strip=True)
        # 简单清洗 title（可选）
        #clean_title = " ".join(title.split())

        # 提取链接
        link = "https://s.weibo.com" + title_tag['href'] if title_tag.get('href') else None

        # 将零散的数据组装进我们定义好的标准契约对象中
        item = HotSearchItem(
            rank=rank_text,
            title=title,
            url=link,
            heat=heat_val,
            latest_crawl_time=current_timestamp
            # first_on_board_time 这里不传，让 Item 类自动使用 latest_crawl_time 作为默认值
        )
        hot_searches.append(item)

        # 打印单条结果（可选）
        #logger.info(f"{rank_text}. {title} (热度: {heat_val}) - {link}")

    return hot_searches

get_realtime_data()

