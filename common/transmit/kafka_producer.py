import json
import logging
from typing import Optional, List, Union
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaProducerWrapper:
    def __init__(self, kafka_servers: Union[str, List[str]]):
        self._send_success_count = 0
        self._send_fail_count = 0
        
        try:
            if isinstance(kafka_servers, str):
                kafka_servers = kafka_servers.split(',')

            self.producer = KafkaProducer(
                bootstrap_servers=kafka_servers,
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k is not None else None,
                retries=3,
                acks=1
            )
            logger.info(f"Kafka Producer 成功挂载至: {kafka_servers}")

        except Exception as e:
            logger.error(f"Kafka Producer 初始化彻底失败: {e}")
            self.producer = None

    def _on_send_success(self, record_metadata):
        self._send_success_count += 1
        logger.debug(f"Kafka消息发送成功: {record_metadata.topic}:{record_metadata.partition}:{record_metadata.offset}")

    def _on_send_error(self, excp):
        self._send_fail_count += 1
        logger.error(f"Kafka消息发送失败: {excp}")

    def send(self, topic: str, message: dict, key: Optional[str] = None):
        if not self.producer:
            logger.warning(f"Kafka 未就绪，丢弃消息: {message.get('title', 'Unknown')}")
            self._send_fail_count += 1
            return

        try:
            future = self.producer.send(topic, key=key, value=message)
            future.add_callback(self._on_send_success)
            future.add_errback(self._on_send_error)
        except KafkaError as e:
            logger.error(f"发送 Kafka 消息失败，Topic={topic}, Error={e}")
            self._send_fail_count += 1

    def get_stats(self) -> dict:
        return {
            'success_count': self._send_success_count,
            'fail_count': self._send_fail_count
        }

    def close(self):
        if self.producer:
            logger.info(f"正在关闭 Kafka Producer，推送剩余消息... 统计: {self.get_stats()}")
            self.producer.flush()
            self.producer.close()
