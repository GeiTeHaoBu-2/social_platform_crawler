import os
import json
import hashlib
import logging

# kafka-python: https://pypi.org/project/kafka-python/
try:
    from kafka import KafkaProducer
    _has_kafka = True
except Exception:
    KafkaProducer = None
    _has_kafka = False

BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
TOPIC = os.getenv('KAFKA_TOPIC', 'weibo.hotsearch')

logger = logging.getLogger(__name__)

producer = None
if _has_kafka:
    try:
        producer = KafkaProducer(
            bootstrap_servers=BOOTSTRAP.split(','),
            value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k is not None else None,
            retries=5
        )
        logger.info(f"Kafka producer initialized for {BOOTSTRAP}")
    except Exception as e:
        logger.exception("Failed to initialize Kafka producer: %s", e)
        # 额外打印到控制台，方便在没有配置 logging 时也能看到错误原因
        print(f"Failed to initialize Kafka producer: {e}")
        producer = None


def _make_id(title: str, source: str = 'weibo') -> str:
    raw = f"{title}_{source}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()


def send_hot_search(hot_search: dict) -> None:
    """
    发送热搜到 Kafka（若 Kafka 不可用则降级为记录日志）。

    hot_search 会自动补充 `id` 字段（md5(title + source)）用于作为 key。
    """
    print("xxxxxxxxxxxxxx1")

    if not _has_kafka or producer is None:
        logger.warning("Kafka not available, skipping send of hot_search: %s", hot_search.get('title'))
        return

    # 保障消息包含 id
    if 'id' not in hot_search or not hot_search.get('id'):
        hot_search['id'] = _make_id(hot_search.get('title', ''), hot_search.get('source', 'weibo'))

    print("xxxxxxxxxxxxxx2")


    key = hot_search['id']
    try:
        print("xxxxxxxxxxxxxx")
        producer.send(TOPIC, key=key, value=hot_search)
        producer.flush(timeout=5)
        logger.info(f"Sent hot_search id={key} to topic={TOPIC}")
    except Exception as e:
        logger.exception("Failed to send hot_search to Kafka: %s", e)
        raise
