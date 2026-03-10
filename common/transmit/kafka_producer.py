import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

logger = logging.getLogger(__name__)


class KafkaProducerWrapper:
    def __init__(self, kafka_servers):
        """
        初始化具有容错机制的 Kafka 生产者
        """
        try:
            # 如果配置传的是字符串(如 'localhost:9092')，转成列表
            if isinstance(kafka_servers, str):
                kafka_servers = kafka_servers.split(',')

            self.producer = KafkaProducer(
                bootstrap_servers=kafka_servers,
                # 1. 解决中文乱码，让 Kafka 里流淌的是纯正的中文字符
                value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
                # 2. 增加 Key 序列化器，保障相同 title 分发到相同 Flink Partition
                key_serializer=lambda k: str(k).encode('utf-8') if k is not None else None,
                # 3. 网络抖动时的自动重试次数
                retries=3,
                # 4. 权衡性能与安全：Leader 写入成功即返回
                acks=1
            )
            logger.info(f"Kafka Producer 成功挂载至: {kafka_servers}")

        except Exception as e:
            logger.error(f"Kafka Producer 初始化彻底失败: {e}")
            self.producer = None

    def send(self, topic: str, message: dict, key: str = None):
        """
        异步发送消息（绝不在内部调用 flush）
        :param topic: 目标 Topic
        :param message: 字典格式的消息体
        :param key: 消息的唯一标识（强烈建议传入热搜的 title）
        """
        if not self.producer:
            logger.warning(f"Kafka 未就绪，丢弃消息: {message.get('title', 'Unknown')}")
            return

        try:
            # 真正的异步发送，极其轻量、极速
            self.producer.send(topic, key=key, value=message)
        except KafkaError as e:
            logger.error(f"发送 Kafka 消息失败，Topic={topic}, Error={e}")

    def close(self):
        """
        优雅关机：只有在整个爬虫流水线结束（或进程退出）时，才调用一次 flush
        将内存中最后一点没发完的数据推送到 Kafka
        """
        if self.producer:
            logger.info("正在关闭 Kafka Producer，推送剩余消息...")
            self.producer.flush()
            self.producer.close()