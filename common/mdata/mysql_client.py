# python
# 文件路径: `common/mdata/mysql_client.py`

import os
import pymysql
from datetime import datetime

# 从环境变量读取配置（可修改为你的配置）
MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "social_platform_analysis")

_inited = False



def _get_conn(db=None):
    params = dict(host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER, password=MYSQL_PASSWORD, charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor, autocommit=True)
    if db:
        params['database'] = db
    return pymysql.connect(**params)



def save_hot_search_to_mysql(item):
    """
    保存单条热搜到 MySQL。
    item 预期字段: rank, title, url, hot_count, tag, first_crawled (unix timestamp 或 datetime)
    """
    first_crawled = item.get('first_crawled')
    if isinstance(first_crawled, (int, float)):
        first_crawled = datetime.fromtimestamp(first_crawled)
    # 插入记录
    sql = """INSERT INTO `weibo_realtime` (`rank`,`title`,`url`,`hot_count`,`tag`,`first_crawled`)
             VALUES (%s,%s,%s,%s,%s,%s)"""
    params = (
        item.get('rank'),
        item.get('title'),
        item.get('url'),
        item.get('hot_count'),
        item.get('tag'),
        first_crawled
    )
    conn = _get_conn(db=MYSQL_DB)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
    finally:
        conn.close()


def save_hot_search_list(items):
    """
    批量保存热搜列表（items 为 dict 列表）。
    """
    if not items:
        return
    sql = """INSERT INTO `weibo_realtime` (`rank`,`title`,`url`,`hot_count`,`tag`,`first_crawled`)
             VALUES (%s,%s,%s,%s,%s,%s)"""
    params_list = []
    for item in items:
        fc = item.get('first_crawled')
        if isinstance(fc, (int, float)):
            fc = datetime.fromtimestamp(fc)
        params_list.append((
            item.get('rank'),
            item.get('title'),
            item.get('url'),
            item.get('hot_count'),
            item.get('tag'),
            fc
        ))
    conn = _get_conn(db=MYSQL_DB)
    try:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)
    finally:
        conn.close()
