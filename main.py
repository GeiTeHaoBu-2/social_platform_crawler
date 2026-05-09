"""
模块名称: main.py
模块职责: 微博热搜监控流水线主入口
"""

import sys
import os
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common.config.settings import CONFIG, config_loader
from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.llm_analyzer import LLMAnalyzer
from common.process.diff_calculator import DiffCalculator
from common.storage.redis_manager import RedisManager
from common.storage.async_writer import AsyncWriter
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.utils.logging_config import logger


class HotSearchPipeline:
    def __init__(self):
        self.cleaner = Cleaner()
        self.analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        self.redis = RedisManager(CONFIG['REDIS'])
        self.diff_calculator = DiffCalculator(self.redis)
        self.writer = AsyncWriter(CONFIG['DB'], platform='weibo')
        self.kafka = KafkaProducerWrapper(CONFIG['KAFKA']['bootstrap_servers'])
        
        self.kafka_topic = CONFIG['KAFKA']['topic']
        self.sleep_seconds = CONFIG['CRAWLER']['sleep_seconds']
        self._running = False
        
        from common.utils.logging_config import add_kafka_handler
        self.kafka_log_handler = add_kafka_handler(self.kafka, topic='python.logs')
        
        self._start_config_reload_thread()
        
        logger.info("HotSearchPipeline初始化完成")
    
    def _start_config_reload_thread(self):
        """启动配置热更新线程"""
        def reload_loop():
            while self._running:
                time.sleep(60)
                
                try:
                    if config_loader.reload_config_if_changed():
                        self._reload_llm_analyzer()
                        
                except Exception as e:
                    logger.error(f"配置热更新失败: {e}")
        
        thread = threading.Thread(target=reload_loop, daemon=True)
        thread.start()
        logger.info("✅ 配置热更新线程已启动")
    
    def _reload_llm_analyzer(self):
        """重新加载LLM分析器"""
        CONFIG['ANALYZER'] = config_loader.get_llm_config()
        
        self.analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        
        logger.info("✅ LLM分析器已重新加载")
    
    def start(self):
        self._running = True
        self.writer.start()
        logger.info("======= 微博热搜监控流水线启动 =======")
    
    def stop(self):
        self._running = False
        self.writer.stop()
        self.kafka.close()
        self.redis.close()
        logger.info("======= 微博热搜监控流水线停止 =======")
    
    def run_once(self):
        try:
            # 1. 爬取
            raw_items = get_realtime_data()
            if not raw_items:
                logger.warning("本次未抓取到数据")
                return
            logger.info(f"[1/7] 爬取成功: {len(raw_items)} 条")
            
            # 2. 清洗
            items = self.cleaner.clean(raw_items)
            if not items:
                logger.warning("清洗后无有效数据")
                return
            logger.info(f"[2/7] 清洗完成: {len(items)} 条")
            
            # 3. 计算差值（在Redis缓存前，因为需要读取上一轮数据）
            current_time = int(time.time())
            diff_result = self.diff_calculator.calculate(items, current_time, 'weibo')
            for item in items:
                item.heat_diff, item.rank_diff = diff_result.get(item.item_id, (0, 0))
            logger.info(f"[3/7] 差值计算完成")
            
            # 4. LLM分析
            result = self.analyzer.process_items(items, CONFIG['REDIS'])
            all_processed = result['all_results']
            new_items = result['new_items']
            analysis_data = result['analysis_results']
            logger.info(f"[4/7] LLM分析完成: 总计{len(all_processed)}条, 新增{len(new_items)}条")
            
            # 4.1 将NLP结果回填到items
            for item in items:
                for p in all_processed:
                    if p.get('item_id') == item.item_id:
                        item.sentiment_score = p.get('sentiment_score')
                        item.type_name = p.get('type_name')
                        item.topic_name = p.get('topic_name')
                        break
            
            # 5. Redis缓存（在LLM分析后，包含NLP结果）
            self.redis.update_rank(items, 'weibo')
            self.redis.save_hot_search(items, 'weibo')
            logger.info("[5/7] Redis缓存更新完成")
            
            # 6. 异步写入MySQL
            # 6.1 写入base表（仅新增）
            for item in new_items:
                self.writer.enqueue_base(item)
            
            # 6.2 写入analysis表
            analysis_items, topic_items = self.analyzer.get_items_for_db_write(analysis_data)
            for item in analysis_items:
                self.writer.enqueue_analysis(item)
            
            # 6.3 写入trend表（全量，不含差值字段）
            for item in items:
                trend_item = {
                    'item_id': item.item_id,
                    'rank_pos': item.rank,
                    'heat': item.heat,
                    'crawl_time': item.latest_crawl_time * 1000
                }
                self.writer.enqueue_trend(trend_item)
            
            logger.info(f"[6/7] 已入队: base={len(new_items)}, analysis={len(analysis_items)}, trend={len(items)} 条")
            
            # 7. 发送Kafka（全量）
            for item in items:
                nlp_result = None
                for p in all_processed:
                    if p.get('item_id') == item.item_id:
                        nlp_result = p
                        break
                
                kafka_msg = item.to_kafka_dict(nlp_result)
                self.kafka.send(
                    topic=self.kafka_topic,
                    message=kafka_msg,
                    key=item.title
                )
            logger.info(f"[7/7] Kafka发送完成: {len(items)} 条")
            
        except Exception as e:
            logger.error(f"流程执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def run_forever(self):
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
    pipeline = HotSearchPipeline()
    pipeline.run_forever()


if __name__ == "__main__":
    main()
