"""
模块名称: mysql_client.py
模块职责: MySQL数据库客户端，负责维度表(weibo_base, weibo_analysis)的批量写入
输入接口: batch_write_base(items), batch_write_analysis(items)
输出格式: 批量写入MySQL，返回操作结果
依赖模块: pymysql, common.models.item.HotSearchItem
作者备注: 
    - 严禁写入weibo_trend表（Flink负责）
    - 严禁写入weibo_current表（已废除）
    - 仅提供批量写入接口，供AsyncWriter调用
"""

import pymysql
import hashlib
from typing import List, Dict, Any
from common.models.item import HotSearchItem
from common.utils.logging_config import logger


class MySQLClient:
    """
    MySQL客户端 - 维度表写入专用
    
    职责边界:
    1. 仅写入 weibo_base 和 weibo_analysis 两张维度表
    2. 严禁写入 weibo_trend（Flink负责）
    3. 严禁写入 weibo_current（表已废除）
    """
    
    def __init__(self, config: Dict[str, Any], platform: str = 'weibo'):
        """
        初始化MySQL客户端
        
        Args:
            config: 数据库配置字典，包含host, port, user, password, database等
            platform: 平台标识，用于推导表名
        """
        try:
            self.connection = pymysql.connect(
                host=config.get('host', '127.0.0.1'),
                port=config.get('port', 3306),
                user=config.get('user', 'root'),
                password=config.get('password', ''),
                database=config.get('database', 'social_platforms_analysis'),
                charset=config.get('charset', 'utf8mb4'),
                autocommit=False  # 批量写入时需要手动控制事务
            )
            
            self.platform = platform
            # 仅保留维度表名，严禁涉及趋势表
            self.table_base = f"{platform}_base"
            self.table_analysis = f"{platform}_analysis"
            
            logger.info(f"MySQL连接成功！目标维度表: {self.table_base}, {self.table_analysis}")
        except Exception as e:
            logger.error(f"MySQL连接失败: {e}")
            raise

    def _generate_item_id(self, title: str) -> str:
        """
        生成item_id - 基于title的MD5哈希
        
        原理: MD5(title)作为全局唯一标识，确保跨系统一致性
        """
        return hashlib.md5(title.encode('utf-8')).hexdigest()

    def batch_write_base(self, items: List[HotSearchItem]) -> int:
        """
        批量写入weibo_base表 - 使用INSERT IGNORE
        
        策略说明:
        - INSERT IGNORE: 保护first_time字段，首次写入后不再更新
        - 适用于记录首次出现的基础信息
        
        Args:
            items: HotSearchItem列表
            
        Returns:
            int: 成功写入的行数
        """
        if not items:
            return 0
        
        params = []
        for item in items:
            item_id = self._generate_item_id(item.title)
            params.append((
                item_id,
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
                # executemany返回最后一次执行的影响行数
                result = cursor.executemany(sql, params)
                self.connection.commit()
                # 对于INSERT IGNORE，返回的是实际插入的行数
                logger.debug(f"成功写入 {len(items)} 条数据到 {self.table_base} 表，影响行数: {result}")
                return len(items)  # 返回处理的条数
        except Exception as e:
            self.connection.rollback()
            logger.error(f"批量写入 {self.table_base} 失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    def batch_write_analysis(self, items: List[Dict[str, Any]]) -> int:
        """
        批量写入weibo_analysis表 - 使用INSERT ... ON DUPLICATE KEY UPDATE
        
        策略说明:
        - ON DUPLICATE KEY UPDATE: 允许更新情感分（缓存过期后重新分析）
        - 严禁使用INSERT IGNORE，必须允许更新
        
        Args:
            items: 包含分析结果的字典列表，格式:
                   [{"item_id": str, "sentiment_score": float, 
                     "type_name": str, "topic_name": str, "nlp_time": int}, ...]
        
        Returns:
            int: 成功写入的行数
        """
        if not items:
            return 0
        
        params = []
        for item in items:
            # 只需要提供INSERT部分的5个参数
            # ON DUPLICATE KEY UPDATE使用VALUES()函数引用插入值
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
                return len(items)  # 返回处理的条数
        except Exception as e:
            self.connection.rollback()
            logger.error(f"批量写入 {self.table_analysis} 失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return 0

    def close(self):
        """优雅关闭连接"""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("MySQL连接已断开。")


if __name__ == '__main__':
    # 简单测试写入
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
    
    # 测试写入base表
    count = client.batch_write_base([test_item])
    print(f"写入base表: {count} 条")
    
    # 测试写入analysis表
    test_analysis = [{
        'item_id': client._generate_item_id(test_item.title),
        'sentiment_score': 0.5,
        'type_name': '娱乐',
        'topic_name': '测试话题',
        'nlp_time': int(datetime.now().timestamp())
    }]
    count = client.batch_write_analysis(test_analysis)
    print(f"写入analysis表: {count} 条")
    
    client.close()
