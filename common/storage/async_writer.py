"""
模块名称: async_writer.py
模块职责: 异步数据库写入器，实现队列+守护线程模式
输入接口: enqueue_base(item), enqueue_analysis(item), start(), stop()
输出格式: 批量写入MySQL维度表
依赖模块: queue, threading, common.storage.mysql_client.MySQLClient
作者备注: 
    - 使用queue.Queue + threading.Thread(daemon=True)
    - 批量阈值：满100条或每5秒强制刷盘
    - 主线程只负责queue.put()，严禁直接操作数据库
"""

import queue
import threading
import time
import hashlib
from typing import Dict, Any, List, Optional
from common.storage.mysql_client import MySQLClient
from common.utils.logging_config import logger


class AsyncWriter:
    """
    异步数据库写入器
    
    架构设计:
    主爬虫线程 ──> Queue ──> 后台守护线程 ──> 批量写入MySQL
    
    批量策略:
    - 数量阈值: 100条
    - 时间阈值: 5秒
    - 程序退出: 尝试清空队列
    """
    
    # 批量写入阈值
    BATCH_SIZE = 100
    # 强制刷盘间隔(秒)
    FLUSH_INTERVAL = 5
    
    def __init__(self, db_config: Dict[str, Any], platform: str = 'weibo'):
        """
        初始化异步写入器
        
        Args:
            db_config: MySQL配置字典
            platform: 平台标识
        """
        self.db_config = db_config
        self.platform = platform
        
        # 初始化两个队列：base表和analysis表分开处理
        self.base_queue = queue.Queue()
        self.analysis_queue = queue.Queue()
        
        # MySQL客户端（在守护线程中使用）
        self.mysql_client: Optional[MySQLClient] = None
        
        # 守护线程控制
        self._stop_event = threading.Event()
        self._base_worker: Optional[threading.Thread] = None
        self._analysis_worker: Optional[threading.Thread] = None
        
        logger.info("AsyncWriter初始化完成")
    
    def start(self):
        """启动异步写入守护线程"""
        # 初始化MySQL连接（在子线程中各自维护连接）
        self.mysql_client = MySQLClient(self.db_config, self.platform)
        
        # 启动base表写入线程
        self._base_worker = threading.Thread(
            target=self._base_writer_loop,
            name="AsyncBaseWriter",
            daemon=True
        )
        self._base_worker.start()
        
        # 启动analysis表写入线程
        self._analysis_worker = threading.Thread(
            target=self._analysis_writer_loop,
            name="AsyncAnalysisWriter",
            daemon=True
        )
        self._analysis_worker.start()
        
        logger.info("异步写入守护线程已启动")
    
    def stop(self):
        """停止异步写入器，尝试清空队列"""
        logger.info("正在停止AsyncWriter，尝试清空队列...")
        self._stop_event.set()
        
        # 等待队列清空（最多5秒）
        timeout = 5
        start_time = time.time()
        while (not self.base_queue.empty() or not self.analysis_queue.empty()) \
              and time.time() - start_time < timeout:
            time.sleep(0.1)
        
        # 强制刷新剩余数据
        self._flush_base()
        self._flush_analysis()
        
        # 关闭MySQL连接
        if self.mysql_client:
            self.mysql_client.close()
        
        logger.info("AsyncWriter已停止")
    
    def enqueue_base(self, item) -> bool:
        """
        将item放入base表写入队列
        
        Args:
            item: HotSearchItem对象
            
        Returns:
            bool: 是否成功入队
        """
        try:
            self.base_queue.put(item, block=False)
            return True
        except queue.Full:
            logger.warning("base_queue已满，丢弃数据")
            return False
    
    def enqueue_analysis(self, item: Dict[str, Any]) -> bool:
        """
        将分析结果放入analysis表写入队列
        
        Args:
            item: 包含分析结果的字典
            
        Returns:
            bool: 是否成功入队
        """
        try:
            self.analysis_queue.put(item, block=False)
            return True
        except queue.Full:
            logger.warning("analysis_queue已满，丢弃数据")
            return False
    
    def _base_writer_loop(self):
        """base表写入守护线程主循环"""
        buffer = []
        last_flush_time = time.time()
        
        while not self._stop_event.is_set() or not self.base_queue.empty():
            try:
                # 非阻塞取数据，超时100ms
                item = self.base_queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass
            
            # 检查是否需要刷盘
            current_time = time.time()
            should_flush = (
                len(buffer) >= self.BATCH_SIZE or
                (buffer and current_time - last_flush_time >= self.FLUSH_INTERVAL)
            )
            
            if should_flush and buffer:
                self._write_base_batch(buffer)
                buffer = []
                last_flush_time = current_time
        
        # 循环结束，刷盘剩余数据
        if buffer:
            self._write_base_batch(buffer)
    
    def _analysis_writer_loop(self):
        """analysis表写入守护线程主循环"""
        buffer = []
        last_flush_time = time.time()
        
        while not self._stop_event.is_set() or not self.analysis_queue.empty():
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
                self._write_analysis_batch(buffer)
                buffer = []
                last_flush_time = current_time
        
        if buffer:
            self._write_analysis_batch(buffer)
    
    def _write_base_batch(self, items: List):
        """批量写入base表"""
        if not items:
            logger.warning("_write_base_batch: items为空列表")
            return
        
        logger.debug(f"_write_base_batch: 准备写入 {len(items)} 条数据")
        logger.debug(f"_write_base_batch: 第一条数据类型={type(items[0])}, 内容={items[0]}")
        
        try:
            count = self.mysql_client.batch_write_base(items)
            logger.info(f"AsyncWriter批量写入 {count} 条到base表")
        except Exception as e:
            logger.error(f"AsyncWriter批量写入base表失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _write_analysis_batch(self, items: List[Dict[str, Any]]):
        """批量写入analysis表"""
        if not items:
            logger.warning("_write_analysis_batch: items为空列表")
            return
        
        logger.debug(f"_write_analysis_batch: 准备写入 {len(items)} 条数据")
        logger.debug(f"_write_analysis_batch: 第一条数据类型={type(items[0])}, 内容={items[0]}")
        
        try:
            count = self.mysql_client.batch_write_analysis(items)
            logger.info(f"AsyncWriter批量写入 {count} 条到analysis表")
        except Exception as e:
            logger.error(f"AsyncWriter批量写入analysis表失败: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _flush_base(self):
        """强制刷空base队列"""
        buffer = []
        while not self.base_queue.empty():
            try:
                buffer.append(self.base_queue.get_nowait())
            except queue.Empty:
                break
        if buffer:
            self._write_base_batch(buffer)
    
    def _flush_analysis(self):
        """强制刷空analysis队列"""
        buffer = []
        while not self.analysis_queue.empty():
            try:
                buffer.append(self.analysis_queue.get_nowait())
            except queue.Empty:
                break
        if buffer:
            self._write_analysis_batch(buffer)


if __name__ == '__main__':
    # 测试代码
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
    
    # 模拟写入
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
            'nlp_time': int(datetime.now().timestamp())
        }
        writer.enqueue_analysis(analysis)
    
    time.sleep(3)
    writer.stop()
