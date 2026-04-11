"""
模块名称: mysql_client.py
模块职责: MySQL数据库客户端，负责维度表(weibo_base, weibo_analysis)的批量写入
"""

import pymysql
from typing import List, Dict, Any
from common.models.item import HotSearchItem
from common.utils.logging_config import logger


class MySQLClient:
    def __init__(self, config: Dict[str, Any], platform: str = 'weibo'):
        try:
            self.connection = pymysql.connect(
                host=config.get('host', '127.0.0.1'),
                port=config.get('port', 3306),
                user=config.get('user', 'root'),
                password=config.get('password', ''),
                database=config.get('database', 'social_platforms_analysis'),
                charset=config.get('charset', 'utf8mb4'),
                autocommit=False
            )
            
            self.platform = platform
            self.table_base = f"{platform}_base"
            self.table_analysis = f"{platform}_analysis"
            
            logger.info(f"MySQL连接成功！目标维度表: {self.table_base}, {self.table_analysis}")
        except Exception as e:
            logger.error(f"MySQL连接失败: {e}")
            raise

    def batch_write_base(self, items: List[HotSearchItem]) -> int:
        if not items:
            return 0
        
        params = []
        for item in items:
            params.append((
                item.item_id,
                item.title,
                item.url,
                item.first_on_board_time
            ))
        
        sql = f"""
            INSERT IGNORE INTO `{self.table_base}` 
            (item_id, title, url, first_time)
            VALUES (%s, %s, %s, %s)
        """
        
        try:
            with self.connection.cursor() as cursor:
                result = cursor.executemany(sql, params)
                self.connection.commit()
                logger.debug(f"成功写入 {len(items)} 条数据到 {self.table_base} 表，影响行数: {result}")
                return len(items)
        except Exception as e:
            self.connection.rollback()
            logger.error(f"批量写入 {self.table_base} 失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    def batch_write_analysis(self, items: List[Dict[str, Any]]) -> int:
        if not items:
            return 0
        
        params = []
        for item in items:
            params.append((
                item['item_id'],
                item['sentiment_score'],
                item['type_name'],
                item['topic_name'],
                item['nlp_time']
            ))
        
        sql = f"""
            INSERT INTO `{self.table_analysis}` 
            (item_id, sentiment_score, type_name, topic_name, nlp_time)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                sentiment_score = VALUES(sentiment_score),
                type_name = VALUES(type_name),
                topic_name = VALUES(topic_name),
                nlp_time = VALUES(nlp_time)
        """
        
        try:
            with self.connection.cursor() as cursor:
                result = cursor.executemany(sql, params)
                self.connection.commit()
                logger.debug(f"成功写入/更新 {len(items)} 条数据到 {self.table_analysis} 表，影响行数: {result}")
                return len(items)
        except Exception as e:
            self.connection.rollback()
            logger.error(f"批量写入 {self.table_analysis} 失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    def close(self):
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("MySQL连接已断开。")


if __name__ == '__main__':
    from datetime import datetime
    
    config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',
        'database': 'social_platforms_analysis',
        'charset': 'utf8mb4'
    }
    
    client = MySQLClient(config=config, platform='weibo')
    test_item = HotSearchItem(
        rank=1,
        title="测试热搜条目",
        url="https://weibo.com/test",
        heat=5000000,
        latest_crawl_time=int(datetime.now().timestamp()),
        first_on_board_time=int(datetime.now().timestamp())
    )
    
    count = client.batch_write_base([test_item])
    print(f"写入base表: {count} 条")
    
    test_analysis = [{
        'item_id': test_item.item_id,
        'sentiment_score': 0.5,
        'type_name': '娱乐',
        'topic_name': '测试话题',
        'nlp_time': int(datetime.now().timestamp())
    }]
    count = client.batch_write_analysis(test_analysis)
    print(f"写入analysis表: {count} 条")
    
    client.close()
