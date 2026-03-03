"""检测 Kafka 连接并打印初始化错误的详细信息（便于排查）。

用法：
  python tools/check_kafka.py

会尝试使用相同的配置初始化 KafkaProducer 并输出结果。
"""
import os
import logging
import json

try:
    from kafka import KafkaProducer
except Exception as e:
    print("❌ 导入 kafka 客户端包失败：")
    print(str(e))
    print("可能是安装了不兼容的 'kafka' 包（非 kafka-python）。请尝试运行：")
    print("  pip uninstall kafka")
    print("  pip install -U kafka-python")
    raise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')

if __name__ == '__main__':
    try:
        print(f"尝试连接 Kafka: {BOOTSTRAP}")
        p = KafkaProducer(bootstrap_servers=BOOTSTRAP.split(','),
                          value_serializer=lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'))
        print("✅ KafkaProducer 初始化成功")
        p.close()
    except Exception as e:
        print("❌ KafkaProducer 初始化失败：")
        logger.exception(e)
        print(str(e))
        raise
