"""
全组件集成测试
一次性测试MySQL、Redis、LLM、Kafka四个组件
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime

from common.config.settings import CONFIG
from common.storage.mysql_client import MySQLClient
from common.storage.redis_manager import RedisManager
from common.process.llm_analyzer import LLMAnalyzer
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.models.item import HotSearchItem


def test_all():
    """执行全组件测试"""
    print("\n" + "=" * 60)
    print("  全组件集成测试")
    print("=" * 60)
    
    results = {
        'mysql': False,
        'redis': False,
        'llm': False,
        'kafka': False
    }
    
    # ==================== 1. MySQL测试 ====================
    print("\n[1/4] MySQL测试...")
    print("-" * 40)
    try:
        client = MySQLClient(CONFIG['DB'], platform='weibo')
        
        # 写入测试数据
        test_item = HotSearchItem(
            rank=1,
            title=f'集成测试_{int(datetime.now().timestamp())}',
            url='https://weibo.com/test',
            heat=9999999,
            latest_crawl_time=int(datetime.now().timestamp()),
            first_on_board_time=int(datetime.now().timestamp())
        )
        
        count = client.batch_write_base([test_item])
        print(f"✓ 写入base表: {count} 条")
        
        test_analysis = [{
            'item_id': client._generate_item_id(test_item.title),
            'sentiment_score': 0.8,
            'type_name': '测试',
            'topic_name': '集成测试话题',
            'nlp_time': int(datetime.now().timestamp())
        }]
        count = client.batch_write_analysis(test_analysis)
        print(f"✓ 写入analysis表: {count} 条")
        
        client.close()
        results['mysql'] = True
        print("✓ MySQL测试通过")
        
    except Exception as e:
        print(f"✗ MySQL测试失败: {e}")
    
    # ==================== 2. Redis测试 ====================
    print("\n[2/4] Redis测试...")
    print("-" * 40)
    try:
        redis_mgr = RedisManager(CONFIG['REDIS'])
        
        if redis_mgr.client is None:
            print("✗ Redis连接失败")
        else:
            # 测试写入和读取
            test_key = "test:integration"
            import json
            redis_mgr.client.setex(test_key, 60, json.dumps({"test": True}))
            result = redis_mgr.client.get(test_key)
            redis_mgr.client.delete(test_key)
            
            results['redis'] = True
            print("✓ Redis测试通过")
        
        redis_mgr.close()
        
    except Exception as e:
        print(f"✗ Redis测试失败: {e}")
    
    # ==================== 3. LLM测试 ====================
    print("\n[3/4] LLM测试...")
    print("-" * 40)
    try:
        analyzer_config = CONFIG['ANALYZER']
        
        if not analyzer_config.get('enabled'):
            print("✗ LLM未启用")
        elif not analyzer_config.get('api_key'):
            print("✗ API Key未配置")
        else:
            analyzer = LLMAnalyzer(analyzer_config)
            result = analyzer.analyze("测试热搜标题")
            
            if result and 'sentiment_score' in result:
                results['llm'] = True
                print(f"✓ LLM分析成功")
                print(f"  - 情感分数: {result.get('sentiment_score')}")
                print(f"  - 类型: {result.get('type_name')}")
            else:
                print("✗ LLM返回结果异常")
        
    except Exception as e:
        print(f"✗ LLM测试失败: {e}")
    
    # ==================== 4. Kafka测试 ====================
    print("\n[4/4] Kafka测试...")
    print("-" * 40)
    try:
        kafka_config = CONFIG['KAFKA']
        producer = KafkaProducerWrapper(kafka_config['bootstrap_servers'])
        
        if producer.producer is None:
            print("✗ Kafka连接失败")
        else:
            # 发送测试消息
            test_msg = {
                "item_id": f"test_{int(datetime.now().timestamp())}",
                "title": "集成测试消息",
                "test": True,
                "timestamp": int(datetime.now().timestamp())
            }
            producer.send(kafka_config['topic'], test_msg, key="test")
            producer.close()
            
            results['kafka'] = True
            print("✓ Kafka测试通过")
        
    except Exception as e:
        print(f"✗ Kafka测试失败: {e}")
    
    # ==================== 测试结果汇总 ====================
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
    
    if passed == total:
        print("\n  🎉 所有组件测试通过！系统可以正常运行")
    else:
        print("\n  ⚠️ 部分组件测试失败，请检查配置")
    
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
