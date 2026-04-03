"""
模块名称: main.py
模块职责: 微博热搜监控流水线主入口，协调爬虫、NLP、缓存、异步写入、Kafka发送
输入接口: 无（主程序入口）
输出格式: 写入MySQL维度表，发送Kafka消息
依赖模块: 
    - common.platforms.sina.getRealtimeWithCrawler
    - common.process.cleaner
    - common.process.nlp_pipeline
    - common.storage.redis_client
    - common.storage.async_writer
    - common.transmit.kafka_producer
作者备注: 
    - 严禁写入weibo_trend表
    - 严禁基于排名/热度变化过滤Kafka消息
    - 所有热搜必须全量发送Kafka
"""

import sys
import os

# 将项目根目录加入模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from typing import Dict, Any, List

from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.nlp_pipeline import NLPPipeline
from common.storage.async_writer import AsyncWriter
from common.storage.redis_client import save_hot_search_to_redis
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.config.settings import (
    MYSQL_CONFIG, REDIS_CONFIG, KAFKA_CONFIG, CRAWLER_CONFIG
)
from common.utils.logging_config import logger


class HotSearchPipeline:
    """
    热搜监控流水线
    
    架构设计:
    1. 配置注入：所有依赖通过构造函数接收
    2. 异步写入：主线程只负责queue.put()，不直接操作数据库
    3. 全量发送：所有热搜必须全量发送Kafka，严禁过滤
    4. 职责分离：Python只写维度表，趋势表由Flink负责
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化流水线
        
        Args:
            config: 完整配置字典，包含DB、Redis、Kafka、Crawler配置
        """
        self.config = config
        
        # Step 1: 初始化清洗器
        self.cleaner = Cleaner()
        
        # Step 2: 初始化NLP流水线（带缓存）
        self.nlp_pipeline = NLPPipeline(redis_config=config.get('REDIS'))
        
        # Step 3: 初始化异步写入器
        self.async_writer = AsyncWriter(
            db_config=config.get('DB'),
            platform='weibo'
        )
        
        # Step 4: 初始化Kafka生产者
        kafka_servers = config.get('KAFKA', {}).get('bootstrap_servers', ['localhost:9092'])
        if isinstance(kafka_servers, str):
            kafka_servers = kafka_servers.split(',')
        self.kafka_producer = KafkaProducerWrapper(kafka_servers)
        
        # Step 5: 获取配置值
        self.kafka_topic = config.get('KAFKA', {}).get('topic', 'weibo_raw')
        self.sleep_seconds = config.get('CRAWLER', {}).get('sleep_seconds', 30)
        
        # 标记运行状态
        self._running = False
        
        logger.info("HotSearchPipeline初始化完成")
    
    def start(self):
        """启动流水线"""
        self._running = True
        # 启动异步写入器
        self.async_writer.start()
        logger.info("======= 微博热搜监控流水线启动 =======")
    
    def stop(self):
        """停止流水线"""
        self._running = False
        # 停止异步写入器
        self.async_writer.stop()
        # 关闭Kafka生产者
        self.kafka_producer.close()
        logger.info("======= 微博热搜监控流水线停止 =======")
    
    def _update_redis_zset(self, items: List, platform: str = 'weibo'):
        """
        更新Redis ZSet实时榜单
        
        Key: weibo:realtime_rank
        Score: 热度值(heat)或排名(rank_pos)
        Member: item_id
        
        目的: 支持前端按热度/排名排序查询
        """
        import json
        import redis
        import hashlib
        
        try:
            # 连接Redis
            redis_client = redis.Redis(
                host=self.config.get('REDIS', {}).get('host', '127.0.0.1'),
                port=self.config.get('REDIS', {}).get('port', 6379),
                db=self.config.get('REDIS', {}).get('db', 0),
                password=self.config.get('REDIS', {}).get('password', None),
                decode_responses=True
            )
            
            zset_key = f"{platform}:realtime_rank"
            
            # 使用pipeline批量操作
            pipeline = redis_client.pipeline()
            
            # 清空旧数据
            pipeline.delete(zset_key)
            
            # 添加新数据
            for item in items:
                item_id = hashlib.md5(item.title.encode('utf-8')).hexdigest()
                # 使用热度作为score（也可以用排名，但热度更有区分度）
                pipeline.zadd(zset_key, {item_id: item.heat})
            
            # 设置过期时间（10分钟）
            pipeline.expire(zset_key, 600)
            
            pipeline.execute()
            logger.debug(f"Redis ZSet已更新: {len(items)} 条")
            
        except Exception as e:
            logger.error(f"更新Redis ZSet失败: {e}")
    
    def run_once(self):
        """
        执行一次完整的爬虫流程
        
        业务流程:
        1. 爬取原始数据
        2. 数据清洗
        3. 更新Redis实时缓存(ZSet)
        4. NLP缓存筛查
        5. 异步队列写入MySQL维度表
        6. 全量发送Kafka（严禁过滤）
        """
        try:
            # ========== Step 1: 爬取原始数据 ==========
            raw_data_items = get_realtime_data()
            if not raw_data_items:
                logger.warning("本次未抓取到数据，流水线中止。")
                return
            logger.info(f"1. 成功爬取到 {len(raw_data_items)} 条热搜对象")
            
            # ========== Step 2: 数据清洗 ==========
            cleaned_items = self.cleaner.clean(raw_data_items)
            if not cleaned_items:
                logger.warning("数据清洗后无有效数据。")
                return
            logger.info(f"2. 数据清洗完成，剩余 {len(cleaned_items)} 条有效数据")
            
            # ========== Step 3: 更新Redis实时缓存 ==========
            try:
                # 更新ZSet榜单（用于前端排序）
                self._update_redis_zset(cleaned_items, 'weibo')
                # 同时更新原有的Redis缓存（兼容旧逻辑）
                save_hot_search_to_redis(cleaned_items, 'weibo')
                logger.info("3. 实时榜单已刷新至Redis")
            except Exception as e:
                logger.error(f"3. Redis更新失败: {e}")
                # Redis失败不影响主流程
            
            # ========== Step 4: NLP缓存筛查 ==========
            # 处理所有items，包括缓存命中和未命中的
            processed_items = self.nlp_pipeline.process_items(cleaned_items)
            logger.info(f"4. NLP处理完成，共 {len(processed_items)} 条（含缓存命中）")
            
            # 分离需要写入DB的items
            base_items, analysis_items = self.nlp_pipeline.get_items_for_db_write(processed_items)
            
            # ========== Step 5: 异步队列写入MySQL ==========
            # 注意：主线程只负责enqueue，不直接操作数据库
            try:
                for item in base_items:
                    self.async_writer.enqueue_base(item)
                for item in analysis_items:
                    self.async_writer.enqueue_analysis(item)
                logger.info(f"5. 已将 {len(base_items)} 条数据放入异步写入队列")
            except Exception as e:
                logger.error(f"5. 异步队列写入失败: {e}")
                # 队列写入失败不影响Kafka发送
            
            # ========== Step 6: 全量发送Kafka（严禁过滤）==========
            # ⚠️ 重要：所有热搜必须全量发送Kafka，严禁基于排名/热度变化过滤
            # 缓存仅用于避免重复NLP计算，不影响Kafka消息发送
            try:
                kafka_count = 0
                for item in processed_items:
                    # 组装Kafka消息（移除调试用字段is_from_cache）
                    kafka_msg = {
                        'item_id': item['item_id'],
                        'title': item['title'],
                        'rank_pos': item['rank_pos'],
                        'heat': item['heat'],
                        'crawl_time': item['crawl_time'],
                        'sentiment_score': item['sentiment_score'],
                        'topic_name': item['topic_name'],
                        'type_name': item['type_name'],
                        'source': item['source']
                    }
                    
                    # 异步发送Kafka
                    self.kafka_producer.send(
                        topic=self.kafka_topic,
                        message=kafka_msg,
                        key=item['title']  # 使用title作为key，确保相同title分到同一partition
                    )
                    kafka_count += 1
                
                logger.info(f"6. 成功将 {kafka_count} 条完整数据推送到Kafka")
            except Exception as e:
                logger.error(f"6. Kafka发送失败: {e}")
                # 单条失败不影响其他数据
        
        except Exception as e:
            logger.error(f"流水线执行失败: {e}")
            # 异常只记录日志，禁止抛出导致程序退出
    
    def run_forever(self):
        """持续运行流水线"""
        self.start()
        try:
            while self._running:
                self.run_once()
                logger.info(f"本轮完成，休眠 {self.sleep_seconds} 秒...\n")
                time.sleep(self.sleep_seconds)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在优雅退出...")
        finally:
            self.stop()


def main():
    """主入口函数"""
    # 组装配置（解耦注入）- 使用小写键名与MySQLClient保持一致
    config = {
        "DB": {
            "host": MYSQL_CONFIG.get('host', '127.0.0.1'),
            "port": MYSQL_CONFIG.get('port', 3306),
            "user": MYSQL_CONFIG.get('user', 'root'),
            "password": MYSQL_CONFIG.get('password', ''),
            "database": MYSQL_CONFIG.get('database', 'social_platforms_analysis'),
            "charset": MYSQL_CONFIG.get('charset', 'utf8mb4')
        },
        "REDIS": {
            "host": REDIS_CONFIG.get('host', '127.0.0.1'),
            "port": REDIS_CONFIG.get('port', 6379),
            "db": REDIS_CONFIG.get('data_db', 0),
            "password": REDIS_CONFIG.get('password', '')
        },
        "KAFKA": {
            "bootstrap_servers": KAFKA_CONFIG.get('servers', ['localhost:9092']),
            "topic": KAFKA_CONFIG.get('topics', {}).get('weibo', 'weibo_raw')
        },
        "CRAWLER": {
            "sleep_seconds": CRAWLER_CONFIG.get('gap_time', 30)
        }
    }
    
    # 创建并运行流水线
    pipeline = HotSearchPipeline(config)
    pipeline.run_forever()


if __name__ == "__main__":
    main()
