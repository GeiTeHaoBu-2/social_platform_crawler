"""
模块名称: kafka_log_handler.py
模块职责: 自定义日志处理器，将日志发送到Kafka

使用示例:
    from common.utils.kafka_log_handler import KafkaLogHandler
    from common.transmit.kafka_producer import KafkaProducerWrapper
    
    # 创建Kafka生产者
    kafka_producer = KafkaProducerWrapper(['localhost:9092'])
    
    # 创建日志处理器
    handler = KafkaLogHandler(kafka_producer, topic='python.logs')
    
    # 添加到logger
    logger.addHandler(handler)

作者: AI Assistant
日期: 2026年5月8日
"""

import logging
import json
import time
import re
from typing import Optional, Dict, Any


class KafkaLogHandler(logging.Handler):
    """
    Kafka日志处理器
    
    职责:
    1. 拦截Python日志
    2. 格式化为JSON
    3. 发送到Kafka
    
    特性:
    - 异步发送，不阻塞主线程
    - 自动过滤敏感信息
    - 失败时静默处理，不影响程序运行
    """
    
    DEFAULT_TOPIC = 'python.logs'
    
    SENSITIVE_PATTERNS = {
        'password': '***',
        'api_key': '***',
        'apikey': '***',
        'cookie': '***',
        'token': '***',
        'secret': '***',
    }
    
    def __init__(self, kafka_producer, topic: Optional[str] = None):
        """
        初始化Kafka日志处理器
        
        Args:
            kafka_producer: KafkaProducerWrapper实例
            topic: Kafka主题名称，默认为 python.logs
        """
        super().__init__()
        self.producer = kafka_producer
        self.topic = topic or self.DEFAULT_TOPIC
        
        self._sent_count = 0
        self._failed_count = 0
        
        print(f"[KafkaLogHandler] 初始化完成，Topic: {self.topic}")
    
    def emit(self, record: logging.LogRecord):
        """
        发送日志到Kafka
        
        Args:
            record: 日志记录对象
        """
        try:
            log_data = self._format_log(record)
            
            self.producer.send(
                topic=self.topic,
                message=log_data,
                key=str(log_data.get('timestamp'))
            )
            
            self._sent_count += 1
            
        except Exception as e:
            self._failed_count += 1
            print(f"[KafkaLogHandler] 发送日志失败: {e}")
    
    def _format_log(self, record: logging.LogRecord) -> Dict[str, Any]:
        """
        格式化日志记录
        
        Args:
            record: 日志记录对象
            
        Returns:
            格式化后的字典
        """
        log_data = {
            'timestamp': int(record.created * 1000),
            'level': record.levelname,
            'logger': record.name,
            'message': self._filter_sensitive(record.getMessage()),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.threadName,
            'source': 'python-crawler'
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatter.formatException(record.exc_info)
        
        if hasattr(record, 'item_id'):
            log_data['item_id'] = record.item_id
        
        if hasattr(record, 'platform'):
            log_data['platform'] = record.platform
        
        return log_data
    
    def _filter_sensitive(self, message: str) -> str:
        """
        过滤敏感信息
        
        Args:
            message: 原始消息
            
        Returns:
            过滤后的消息
        """
        filtered = message
        for key, replacement in self.SENSITIVE_PATTERNS.items():
            pattern = rf'({key}\s*[=:]\s*)\S+'
            filtered = re.sub(pattern, rf'\1{replacement}', filtered, flags=re.IGNORECASE)
        
        return filtered
    
    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        total = self._sent_count + self._failed_count
        return {
            'sent_count': self._sent_count,
            'failed_count': self._failed_count,
            'success_rate': self._sent_count / max(total, 1) * 100
        }


class LogFilter:
    """
    日志过滤器
    
    职责:
    1. 根据级别过滤日志
    2. 根据关键词过滤日志
    3. 控制日志发送频率
    """
    
    def __init__(self, min_level: str = 'INFO', max_rate: int = 100):
        """
        初始化日志过滤器
        
        Args:
            min_level: 最低日志级别
            max_rate: 每秒最大发送数量
        """
        self.min_level = min_level
        self.max_rate = max_rate
        
        self.level_map = {
            'DEBUG': 10,
            'INFO': 20,
            'WARNING': 30,
            'ERROR': 40,
            'CRITICAL': 50
        }
        
        self._sent_this_second = 0
        self._last_second = time.time()
    
    def should_send(self, record: logging.LogRecord) -> bool:
        """
        判断是否应该发送日志
        
        Args:
            record: 日志记录对象
            
        Returns:
            True: 发送
            False: 过滤掉
        """
        record_level = self.level_map.get(record.levelname, 0)
        min_level_value = self.level_map.get(self.min_level, 0)
        
        if record_level < min_level_value:
            return False
        
        current_time = time.time()
        if current_time - self._last_second >= 1.0:
            self._sent_this_second = 0
            self._last_second = current_time
        
        if self._sent_this_second >= self.max_rate:
            return False
        
        self._sent_this_second += 1
        return True


def setup_kafka_logging(kafka_producer, topic: Optional[str] = None, 
                        min_level: str = 'INFO') -> KafkaLogHandler:
    """
    快速设置Kafka日志
    
    Args:
        kafka_producer: KafkaProducerWrapper实例
        topic: Kafka主题
        min_level: 最低日志级别
        
    Returns:
        KafkaLogHandler实例
    """
    from common.utils.logging_config import logger
    
    handler = KafkaLogHandler(kafka_producer, topic)
    
    formatter = logging.Formatter('[%(levelname)s] - %(message)s')
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    logger.info(f"✅ Kafka日志处理器已启用，Topic: {handler.topic}")
    
    return handler


if __name__ == '__main__':
    print("KafkaLogHandler 模块测试")
    print("请通过 main.py 进行集成测试")
