"""
爬虫组件测试
测试 MySQL、Redis、Kafka 连接和基本操作
"""
import sys
import time
import json
from datetime import datetime

sys.path.insert(0, '.')

from common.config.settings import CONFIG
from common.storage.mysql_client import MySQLClient
from common.storage.redis_manager import RedisManager
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.models.item import HotSearchItem


def test_mysql():
    """测试 MySQL 连接和操作"""
    print("\n" + "=" * 50)
    print("MySQL 测试")
    print("=" * 50)
    
    try:
        print("[1/3] 测试连接...")
        client = MySQLClient(CONFIG['DB'], platform='weibo')
        print("✓ MySQL 连接成功")
        
        print("\n[2/3] 测试写入 base 表...")
        test_item = HotSearchItem(
            rank=1,
            title=f'测试热搜_{int(datetime.now().timestamp())}',
            url='https://weibo.com/test',
            heat=9999999,
            latest_crawl_time=int(datetime.now().timestamp()),
            first_on_board_time=int(datetime.now().timestamp())
        )
        count = client.batch_write_base([test_item])
        print(f"✓ 写入 base 表: {count} 条")
        
        print("\n[3/3] 测试写入 trend 表...")
        trend_item = {
            'item_id': test_item.item_id,
            'rank_pos': 1,
            'heat': 9999999,
            'heat_velocity': 100.5,
            'rank_velocity': -0.5,
            'crawl_time': int(datetime.now().timestamp() * 1000)
        }
        count = client.batch_write_trend([trend_item])
        print(f"✓ 写入 trend 表: {count} 条")
        
        client.close()
        print("\n✓ MySQL 测试通过")
        return True
        
    except Exception as e:
        print(f"✗ MySQL 测试失败: {e}")
        return False


def test_redis():
    """测试 Redis 连接和操作"""
    print("\n" + "=" * 50)
    print("Redis 测试")
    print("=" * 50)
    
    try:
        print("[1/3] 测试连接...")
        redis_mgr = RedisManager(CONFIG['REDIS'])
        
        if redis_mgr.client is None:
            print("✗ Redis 连接失败")
            return False
        
        redis_mgr.client.ping()
        print("✓ Redis 连接成功")
        
        print("\n[2/3] 测试写入...")
        test_key = "test:connection"
        test_value = {"status": "ok", "test": True}
        redis_mgr.client.setex(test_key, 60, json.dumps(test_value, ensure_ascii=False))
        print(f"✓ 写入测试数据: {test_key}")
        
        print("\n[3/3] 测试读取...")
        result = redis_mgr.client.get(test_key)
        if result:
            print(f"✓ 读取成功: {result}")
        else:
            print("✗ 读取失败")
            return False
        
        redis_mgr.client.delete(test_key)
        redis_mgr.close()
        
        print("\n✓ Redis 测试通过")
        return True
        
    except Exception as e:
        print(f"✗ Redis 测试失败: {e}")
        return False


def test_kafka():
    """测试 Kafka 连接和发送"""
    print("\n" + "=" * 50)
    print("Kafka 测试")
    print("=" * 50)
    
    try:
        print("[1/3] 检查配置...")
        kafka_config = CONFIG['KAFKA']
        servers = kafka_config.get('bootstrap_servers', [])
        topic = kafka_config.get('topic', 'weibo.hotsearch')
        print(f"✓ Servers: {servers}")
        print(f"✓ Topic: {topic}")
        
        print("\n[2/3] 测试连接...")
        producer = KafkaProducerWrapper(servers)
        
        if producer.producer is None:
            print("✗ Kafka 连接失败")
            return False
        
        print("✓ Kafka 连接成功")
        
        print("\n[3/3] 测试发送消息...")
        test_msg = {
            "itemId": f"test_{int(datetime.now().timestamp())}",
            "title": "测试消息",
            "heat": 1000000,
            "test": True
        }
        producer.send(topic, test_msg, key="test")
        time.sleep(1)
        print(f"✓ 发送测试消息成功")
        
        producer.close()
        
        print("\n✓ Kafka 测试通过")
        return True
        
    except Exception as e:
        print(f"✗ Kafka 测试失败: {e}")
        return False


def test_all():
    """运行所有组件测试"""
    print("\n" + "=" * 60)
    print("  爬虫组件测试")
    print("=" * 60)
    
    results = {
        'mysql': test_mysql(),
        'redis': test_redis(),
        'kafka': test_kafka()
    }
    
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, status in results.items():
        icon = "✓" if status else "✗"
        status_text = "通过" if status else "失败"
        print(f"  {icon} {name.upper():8} : {status_text}")
    
    print("-" * 60)
    print(f"  总计: {passed}/{total} 通过")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
