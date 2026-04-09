"""
模块名称: main.py
模块职责: 微博热搜监控流水线主入口，简洁版流程控制
输入接口: 无（主程序入口）
输出格式: 写入MySQL维度表，发送Kafka消息
作者备注: 
    - 只控制流程，具体逻辑委托给各模块
    - 强制使用LLM分析器（带Redis缓存）
    - Kafka发送完整字段：item_id, title, rank_pos, heat, crawl_time, sentiment_score, topic_name, type_name, source
    - 严禁写入weibo_trend表
    - 所有热搜必须全量发送Kafka
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config.settings import CONFIG
from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.llm_analyzer import LLMAnalyzer
from common.storage.redis_manager import RedisManager
from common.storage.async_writer import AsyncWriter
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.utils.logging_config import logger


class HotSearchPipeline:
    """热搜监控流水线"""
    
    def __init__(self):
        self.cleaner = Cleaner()
        # LLM分析器，传入API配置和Redis配置（用于结果缓存）
        self.analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        self.redis = RedisManager(CONFIG['REDIS'])
        self.writer = AsyncWriter(CONFIG['DB'], platform='weibo')
        self.kafka = KafkaProducerWrapper(CONFIG['KAFKA']['bootstrap_servers'])
        
        self.kafka_topic = CONFIG['KAFKA']['topic']
        self.sleep_seconds = CONFIG['CRAWLER']['sleep_seconds']
        self._running = False
        
        logger.info("HotSearchPipeline初始化完成")
    
    def start(self):
        """启动流水线"""
        self._running = True
        self.writer.start()
        logger.info("======= 微博热搜监控流水线启动 =======")
    
    def stop(self):
        """停止流水线"""
        self._running = False
        self.writer.stop()
        self.kafka.close()
        self.redis.close()
        logger.info("======= 微博热搜监控流水线停止 =======")
    
    def run_once(self):
        """执行一次完整的爬虫流程"""
        try:
            # 1. 爬取
            raw_items = get_realtime_data()
            if not raw_items:
                logger.warning("本次未抓取到数据")
                return
            logger.info(f"[1/6] 爬取成功: {len(raw_items)} 条")
            
            # 2. 清洗
            items = self.cleaner.clean(raw_items)
            if not items:
                logger.warning("清洗后无有效数据")
                return
            logger.info(f"[2/6] 清洗完成: {len(items)} 条")
            
            # 3. Redis缓存
            self.redis.update_rank(items, 'weibo')
            self.redis.save_hot_search(items, 'weibo')
            logger.info("[3/6] Redis缓存更新完成")
            
            # 4. LLM分析（带缓存，返回增量信息）
            result = self.analyzer.process_items(items, CONFIG['REDIS'])
            all_processed = result['all_results']  # 所有处理后的数据（用于Kafka）
            new_items = result['new_items']        # 新增的热搜（缓存未命中，写入base表）
            analysis_data = result['analysis_results']  # 分析结果（写入analysis表）
            logger.info(f"[4/6] LLM分析完成: 总计{len(all_processed)}条, 新增{len(new_items)}条")
            
            # 5. 异步写入MySQL
            # 5.1 写入base表（仅新增的热搜，即缓存未命中的）
            for item in new_items:
                self.writer.enqueue_base(item)
            
            # 5.2 写入analysis表（所有分析结果，用于更新分析数据）
            analysis_items, topic_items = self.analyzer.get_items_for_db_write(analysis_data)
            for item in analysis_items:
                self.writer.enqueue_analysis(item)
            
            logger.info(f"[5/6] 已入队: base={len(new_items)}, analysis={len(analysis_items)} 条待写入")
            
            # 6. 发送Kafka（全量，严禁过滤）
            # 验证并发送完整格式的数据
            for item in all_processed:
                # 确保Kafka消息格式完整
                kafka_msg = {
                    'item_id': item.get('item_id', ''),
                    'title': item.get('title', ''),
                    'rank_pos': item.get('rank_pos', 0),
                    'heat': item.get('heat', 0),
                    'crawl_time': item.get('crawl_time', int(time.time())),
                    'sentiment_score': item.get('sentiment_score', 0.0),
                    'topic_name': item.get('topic_name', ''),
                    'type_name': item.get('type_name', '其他'),
                    'source': item.get('source', 'weibo')
                }
                
                self.kafka.send(
                    topic=self.kafka_topic,
                    message=kafka_msg,
                    key=item.get('title', '')
                )
            logger.info(f"[6/6] Kafka发送完成: {len(all_processed)} 条")
            
        except Exception as e:
            logger.error(f"流程执行失败: {e}")
    
    def run_forever(self):
        """持续运行"""
        self.start()
        try:
            while self._running:
                self.run_once()
                logger.info(f"本轮完成，休眠 {self.sleep_seconds} 秒...\n")
                time.sleep(self.sleep_seconds)
        except KeyboardInterrupt:
            logger.info("收到中断信号，正在退出...")
        finally:
            self.stop()


def main():
    """主入口"""
    pipeline = HotSearchPipeline()
    pipeline.run_forever()


if __name__ == "__main__":
    main()
