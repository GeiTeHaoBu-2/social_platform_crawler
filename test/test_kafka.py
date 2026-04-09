"""
Kafka连接测试
"""
import sys
import time
sys.path.insert(0, '.')

from common.transmit.kafka_producer import KafkaProducerWrapper
from common.config.settings import CONFIG


def test_kafka():
    """测试Kafka连接和发送"""
    print("=" * 50)
    print("Kafka连接测试")
    print("=" * 50)
    
    try:
        # 1. 检查配置
        print("\n[1/4] 检查配置...")
        kafka_config = CONFIG['KAFKA']
        servers = kafka_config.get('bootstrap_servers', [])
        topic = kafka_config.get('topic', 'weibo.hotsearch')
        
        print(f"✓ 配置信息:")
        print(f"  - Servers: {servers}")
        print(f"  - Topic: {topic}")
        
        # 2. 测试连接
        print("\n[2/4] 测试连接...")
        producer = KafkaProducerWrapper(servers)
        
        if producer.producer is None:
            print("✗ Kafka连接失败")
            return False
        
        print("✓ Kafka连接成功")
        
        # 3. 测试发送消息
        print("\n[3/4] 测试发送消息...")
        test_messages = [
            {"item_id": "test_001", "title": "测试消息1", "heat": 1000000, "test": True},
            {"item_id": "test_002", "title": "测试消息2", "heat": 2000000, "test": True},
            {"item_id": "test_003", "title": "测试消息3", "heat": 3000000, "test": True},
        ]
        
        for msg in test_messages:
            producer.send(topic, msg, key=msg['title'])
            print(f"  ✓ 发送: {msg['title']}")
        
        # 等待发送完成
        time.sleep(1)
        print(f"✓ 已发送 {len(test_messages)} 条测试消息")
        
        # 4. 关闭连接
        print("\n[4/4] 关闭连接...")
        producer.close()
        print("✓ Kafka连接已关闭")
        
        print("\n" + "=" * 50)
        print("✓ Kafka测试全部通过!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"✗ Kafka测试失败: {e}")
        return False


if __name__ == "__main__":
    test_kafka()
