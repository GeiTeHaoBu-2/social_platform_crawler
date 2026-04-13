"""
集成测试
测试完整爬虫流程（含 LLM 分析）
"""
import sys
import time
from datetime import datetime

sys.path.insert(0, '.')

from common.config.settings import CONFIG
from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.velocity_calculator import VelocityCalculator
from common.process.llm_analyzer import LLMAnalyzer
from common.storage.redis_manager import RedisManager
from common.storage.async_writer import AsyncWriter
from common.transmit.kafka_producer import KafkaProducerWrapper


def test_crawler():
    """测试爬虫数据采集"""
    print("\n" + "=" * 50)
    print("爬虫采集测试")
    print("=" * 50)
    
    try:
        print("[1/2] 测试爬取...")
        items = get_realtime_data()
        
        if not items:
            print("✗ 未爬取到数据，请检查 Cookie")
            return False
        
        print(f"✓ 爬取成功: {len(items)} 条")
        
        print("\n[2/2] 查看数据样例...")
        sample = items[0]
        print(f"  - 排名: {sample.rank}")
        print(f"  - 标题: {sample.title[:30]}...")
        print(f"  - 热度: {sample.heat}")
        print(f"  - ID: {sample.item_id[:16]}...")
        
        print("\n✓ 爬虫测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 爬虫测试失败: {e}")
        return False


def test_llm():
    """测试 LLM 分析"""
    print("\n" + "=" * 50)
    print("LLM 分析测试")
    print("=" * 50)
    
    try:
        print("[1/2] 初始化 LLM 分析器...")
        analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        print("✓ LLM 分析器初始化成功")
        
        print("\n[2/2] 测试分析...")
        test_title = "某明星官宣结婚引发热议"
        result = analyzer.analyze(test_title)
        
        if result:
            print(f"✓ 分析成功:")
            print(f"  - 情感分数: {result.get('sentiment_score', 0)}")
            print(f"  - 类型: {result.get('type_name', '未知')}")
            print(f"  - 话题: {result.get('topic_name', '未知')}")
        else:
            print("✗ 分析返回空结果")
            return False
        
        print("\n✓ LLM 测试通过")
        return True
        
    except Exception as e:
        print(f"✗ LLM 测试失败: {e}")
        return False


def test_full_pipeline():
    """测试完整流程（不写入数据库）"""
    print("\n" + "=" * 50)
    print("完整流程测试")
    print("=" * 50)
    
    try:
        # 初始化组件
        cleaner = Cleaner()
        redis = RedisManager(CONFIG['REDIS'])
        velocity_calculator = VelocityCalculator(redis)
        analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        
        # 1. 爬取
        print("[1/5] 爬取数据...")
        items = get_realtime_data()
        if not items:
            print("✗ 爬取失败")
            return False
        print(f"✓ 爬取: {len(items)} 条")
        
        # 2. 清洗
        print("\n[2/5] 数据清洗...")
        items = cleaner.clean(items)
        print(f"✓ 清洗: {len(items)} 条")
        
        # 3. 计算加速度
        print("\n[3/5] 计算加速度...")
        current_time = int(time.time())
        velocity_result = velocity_calculator.calculate(items, current_time, 'weibo')
        for item in items:
            item.heat_velocity, item.rank_velocity = velocity_result.get(item.item_id, (0.0, 0.0))
        print(f"✓ 加速度计算完成")
        
        # 4. LLM 分析
        print("\n[4/5] LLM 分析...")
        result = analyzer.process_items(items[:3], CONFIG['REDIS'])  # 只分析前3条
        print(f"✓ 分析: {len(result['all_results'])} 条")
        
        # 5. Redis 缓存
        print("\n[5/5] Redis 缓存...")
        redis.update_rank(items, 'weibo')
        redis.save_hot_search(items, 'weibo')
        print("✓ Redis 缓存完成")
        
        redis.close()
        
        print("\n✓ 完整流程测试通过")
        return True
        
    except Exception as e:
        print(f"✗ 完整流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all():
    """运行所有集成测试"""
    print("\n" + "=" * 60)
    print("  集成测试")
    print("=" * 60)
    
    results = {
        'crawler': test_crawler(),
        'llm': test_llm(),
        'pipeline': test_full_pipeline()
    }
    
    print("\n" + "=" * 60)
    print("  测试结果汇总")
    print("=" * 60)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, status in results.items():
        icon = "✓" if status else "✗"
        status_text = "通过" if status else "失败"
        print(f"  {icon} {name.upper():10} : {status_text}")
    
    print("-" * 60)
    print(f"  总计: {passed}/{total} 通过")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
