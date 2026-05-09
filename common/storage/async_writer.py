"""
模块名称: async_writer.py
模块职责: 异步数据库写入器，实现队列+守护线程模式

修复记录:
- 2026-05-08: 修复MySQL未就绪时线程终止导致数据丢失的bug
  - 增加启动前MySQL连接检查
  - 线程内实现自动重连机制
"""

import queue
import threading
import time
import hashlib
from typing import Dict, Any, List, Optional
from common.storage.mysql_client import MySQLClient
from common.utils.logging_config import logger


class AsyncWriter:
    BATCH_SIZE = 100
    FLUSH_INTERVAL = 5
    MYSQL_RETRY_INTERVAL = 5
    MYSQL_MAX_RETRIES = 10
    
    def __init__(self, db_config: Dict[str, Any], platform: str = 'weibo'):
        self.db_config = db_config
        self.platform = platform
        
        self.base_queue = queue.Queue()
        self.analysis_queue = queue.Queue()
        self.trend_queue = queue.Queue()
        
        self._base_mysql_client: Optional[MySQLClient] = None
        self._analysis_mysql_client: Optional[MySQLClient] = None
        self._trend_mysql_client: Optional[MySQLClient] = None
        
        self._stop_event = threading.Event()
        self._base_worker: Optional[threading.Thread] = None
        self._analysis_worker: Optional[threading.Thread] = None
        self._trend_worker: Optional[threading.Thread] = None
        
        logger.info("AsyncWriter初始化完成")
    
    def _ensure_mysql_ready(self) -> bool:
        """
        启动前检查MySQL连接是否可用
        
        Returns:
            True: MySQL已就绪
            False: MySQL未就绪（但允许继续启动，由线程内重连）
        """
        try:
            test_client = MySQLClient(self.db_config, self.platform)
            test_client.close()
            logger.info("✅ MySQL连接测试成功，数据库已就绪")
            return True
        except Exception as e:
            logger.warning(f"⚠️  MySQL连接测试失败: {e}")
            logger.warning(f"   将在后台线程中持续尝试重连...")
            return False
    
    def start(self):
        self._ensure_mysql_ready()
        
        self._base_worker = threading.Thread(
            target=self._base_writer_loop,
            name="AsyncBaseWriter",
            daemon=True
        )
        self._base_worker.start()
        
        self._analysis_worker = threading.Thread(
            target=self._analysis_writer_loop,
            name="AsyncAnalysisWriter",
            daemon=True
        )
        self._analysis_worker.start()
        
        self._trend_worker = threading.Thread(
            target=self._trend_writer_loop,
            name="AsyncTrendWriter",
            daemon=True
        )
        self._trend_worker.start()
        
        logger.info("异步写入守护线程已启动（base/analysis/trend）")
    
    def stop(self):
        logger.info("正在停止AsyncWriter，尝试清空队列...")
        self._stop_event.set()
        
        timeout = 5
        start_time = time.time()
        while (not self.base_queue.empty() or not self.analysis_queue.empty() or not self.trend_queue.empty()) \
              and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        if self._base_worker and self._base_worker.is_alive():
            self._base_worker.join(timeout=2)
        if self._analysis_worker and self._analysis_worker.is_alive():
            self._analysis_worker.join(timeout=2)
        if self._trend_worker and self._trend_worker.is_alive():
            self._trend_worker.join(timeout=2)
        
        logger.info("AsyncWriter已停止")
    
    def enqueue_base(self, item) -> bool:
        try:
            self.base_queue.put(item, block=False)
            return True
        except queue.Full:
            logger.warning("base_queue已满，丢弃数据")
            return False
    
    def enqueue_analysis(self, item: Dict[str, Any]) -> bool:
        try:
            self.analysis_queue.put(item, block=False)
            return True
        except queue.Full:
            logger.warning("analysis_queue已满，丢弃数据")
            return False
    
    def enqueue_trend(self, item: Dict[str, Any]) -> bool:
        try:
            self.trend_queue.put(item, block=False)
            return True
        except queue.Full:
            logger.warning("trend_queue已满，丢弃数据")
            return False
    
    def _base_writer_loop(self):
        buffer = []
        last_flush_time = time.time()
        reconnect_attempts = 0
        
        while not self._stop_event.is_set() or not self.base_queue.empty():
            if self._base_mysql_client is None:
                try:
                    self._base_mysql_client = MySQLClient(self.db_config, self.platform)
                    logger.info("✅ [BaseWriter] MySQL连接已创建")
                    reconnect_attempts = 0
                except Exception as e:
                    reconnect_attempts += 1
                    if reconnect_attempts <= 3 or reconnect_attempts % 10 == 0:
                        logger.warning(f"⚠️  [BaseWriter] MySQL连接失败 (第{reconnect_attempts}次): {e}")
                    time.sleep(self.MYSQL_RETRY_INTERVAL)
                    continue
            
            try:
                item = self.base_queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass
            
            current_time = time.time()
            should_flush = (
                len(buffer) >= self.BATCH_SIZE or
                (buffer and current_time - last_flush_time >= self.FLUSH_INTERVAL)
            )
            
            if should_flush and buffer:
                try:
                    self._write_base_batch(buffer)
                    buffer = []
                    last_flush_time = current_time
                except Exception as e:
                    logger.error(f"❌ [BaseWriter] 写入失败，将重试: {e}")
                    self._base_mysql_client = None
        
        if buffer:
            self._write_base_batch(buffer)
        
        if self._base_mysql_client:
            self._base_mysql_client.close()
            logger.info("[BaseWriter] MySQL连接已关闭")
    
    def _analysis_writer_loop(self):
        buffer = []
        last_flush_time = time.time()
        reconnect_attempts = 0
        
        while not self._stop_event.is_set() or not self.analysis_queue.empty():
            if self._analysis_mysql_client is None:
                try:
                    self._analysis_mysql_client = MySQLClient(self.db_config, self.platform)
                    logger.info("✅ [AnalysisWriter] MySQL连接已创建")
                    reconnect_attempts = 0
                except Exception as e:
                    reconnect_attempts += 1
                    if reconnect_attempts <= 3 or reconnect_attempts % 10 == 0:
                        logger.warning(f"⚠️  [AnalysisWriter] MySQL连接失败 (第{reconnect_attempts}次): {e}")
                    time.sleep(self.MYSQL_RETRY_INTERVAL)
                    continue
            
            try:
                item = self.analysis_queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass
            
            current_time = time.time()
            should_flush = (
                len(buffer) >= self.BATCH_SIZE or
                (buffer and current_time - last_flush_time >= self.FLUSH_INTERVAL)
            )
            
            if should_flush and buffer:
                try:
                    self._write_analysis_batch(buffer)
                    buffer = []
                    last_flush_time = current_time
                except Exception as e:
                    logger.error(f"❌ [AnalysisWriter] 写入失败，将重试: {e}")
                    self._analysis_mysql_client = None
        
        if buffer:
            self._write_analysis_batch(buffer)
        
        if self._analysis_mysql_client:
            self._analysis_mysql_client.close()
            logger.info("[AnalysisWriter] MySQL连接已关闭")
    
    def _trend_writer_loop(self):
        buffer = []
        last_flush_time = time.time()
        reconnect_attempts = 0
        
        while not self._stop_event.is_set() or not self.trend_queue.empty():
            if self._trend_mysql_client is None:
                try:
                    self._trend_mysql_client = MySQLClient(self.db_config, self.platform)
                    logger.info("✅ [TrendWriter] MySQL连接已创建")
                    reconnect_attempts = 0
                except Exception as e:
                    reconnect_attempts += 1
                    if reconnect_attempts <= 3 or reconnect_attempts % 10 == 0:
                        logger.warning(f"⚠️  [TrendWriter] MySQL连接失败 (第{reconnect_attempts}次): {e}")
                    time.sleep(self.MYSQL_RETRY_INTERVAL)
                    continue
            
            try:
                item = self.trend_queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass
            
            current_time = time.time()
            should_flush = (
                len(buffer) >= self.BATCH_SIZE or
                (buffer and current_time - last_flush_time >= self.FLUSH_INTERVAL)
            )
            
            if should_flush and buffer:
                try:
                    self._write_trend_batch(buffer)
                    buffer = []
                    last_flush_time = current_time
                except Exception as e:
                    logger.error(f"❌ [TrendWriter] 写入失败，将重试: {e}")
                    self._trend_mysql_client = None
        
        if buffer:
            self._write_trend_batch(buffer)
        
        if self._trend_mysql_client:
            self._trend_mysql_client.close()
            logger.info("[TrendWriter] MySQL连接已关闭")
    
    def _write_base_batch(self, items: List):
        if not items or not self._base_mysql_client:
            return
        try:
            count = self._base_mysql_client.batch_write_base(items)
            logger.info(f"[BaseWriter] 成功写入 {count} 条到base表")
        except Exception as e:
            logger.error(f"[BaseWriter] 批量写入base表失败: {e}")
    
    def _write_analysis_batch(self, items: List[Dict[str, Any]]):
        if not items or not self._analysis_mysql_client:
            return
        try:
            count = self._analysis_mysql_client.batch_write_analysis(items)
            logger.info(f"[AnalysisWriter] 成功写入 {count} 条到analysis表")
        except Exception as e:
            logger.error(f"[AnalysisWriter] 批量写入analysis表失败: {e}")
    
    def _write_trend_batch(self, items: List[Dict[str, Any]]):
        if not items or not self._trend_mysql_client:
            return
        try:
            count = self._trend_mysql_client.batch_write_trend(items)
            logger.info(f"[TrendWriter] 成功写入 {count} 条到trend表")
        except Exception as e:
            logger.error(f"[TrendWriter] 批量写入trend表失败: {e}")


if __name__ == '__main__':
    from datetime import datetime
    from common.models.item import HotSearchItem
    
    config = {
        'host': '127.0.0.1',
        'port': 3306,
        'user': 'root',
        'password': '',
        'database': 'social_platforms_analysis',
        'charset': 'utf8mb4'
    }
    
    writer = AsyncWriter(config, platform='weibo')
    writer.start()
    
    for i in range(10):
        item = HotSearchItem(
            rank=i+1,
            title=f"测试热搜{i}",
            url=f"https://weibo.com/test{i}",
            heat=1000000,
            latest_crawl_time=int(datetime.now().timestamp())
        )
        writer.enqueue_base(item)
        
        analysis = {
            'item_id': hashlib.md5(f"测试热搜{i}".encode()).hexdigest(),
            'sentiment_score': 0.5,
            'type_name': '娱乐',
            'topic_name': f'测试话题{i}',
            'llm_time': int(datetime.now().timestamp())
        }
        writer.enqueue_analysis(analysis)
        
        trend = {
            'item_id': hashlib.md5(f"测试热搜{i}".encode()).hexdigest(),
            'rank_pos': i+1,
            'heat': 1000000,
            'crawl_time': int(datetime.now().timestamp() * 1000)
        }
        writer.enqueue_trend(trend)
    
    time.sleep(3)
    writer.stop()
