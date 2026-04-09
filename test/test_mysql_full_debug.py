"""
MySQL写入全流程调试脚本
测试从数据爬取到MySQL写入的完整流程，精确定位问题
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime
from common.config.settings import CONFIG
from common.models.item import HotSearchItem
from common.storage.mysql_client import MySQLClient
from common.storage.async_writer import AsyncWriter
from common.utils.logging_config import logger


def test_mysql_connection():
    """测试MySQL连接是否正常"""
    print("=" * 60)
    print("测试1: MySQL连接测试")
    print("=" * 60)
    
    try:
        client = MySQLClient(CONFIG['DB'], platform='weibo')
        print(f"✓ MySQL连接成功")
        print(f"  - 目标表: {client.table_base}, {client.table_analysis}")
        client.close()
        return True
    except Exception as e:
        print(f"✗ MySQL连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_write_base():
    """测试base表批量写入"""
    print("\n" + "=" * 60)
    print("测试2: base表批量写入测试")
    print("=" * 60)
    
    try:
        client = MySQLClient(CONFIG['DB'], platform='weibo')
        
        # 创建测试数据
        current_time = int(time.time())
        test_items = [
            HotSearchItem(
                rank=1,
                title=f"测试热搜基础写入_{current_time}_1",
                url="https://weibo.com/test1",
                heat=1000000,
                latest_crawl_time=current_time
            ),
            HotSearchItem(
                rank=2,
                title=f"测试热搜基础写入_{current_time}_2",
                url="https://weibo.com/test2",
                heat=900000,
                latest_crawl_time=current_time
            )
        ]
        
        print(f"准备写入 {len(test_items)} 条测试数据到base表")
        for i, item in enumerate(test_items):
            print(f"  [{i}] title={item.title}, type={type(item)}, first_time={item.first_on_board_time}")
        
        count = client.batch_write_base(test_items)
        print(f"✓ base表写入结果: {count} 条")
        
        client.close()
        return count > 0
    except Exception as e:
        print(f"✗ base表写入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_batch_write_analysis():
    """测试analysis表批量写入"""
    print("\n" + "=" * 60)
    print("测试3: analysis表批量写入测试")
    print("=" * 60)
    
    try:
        client = MySQLClient(CONFIG['DB'], platform='weibo')
        
        # 先确保base表有对应数据
        current_time = int(time.time())
        base_item = HotSearchItem(
            rank=1,
            title=f"测试热搜分析写入_{current_time}",
            url="https://weibo.com/test_analysis",
            heat=1000000,
            latest_crawl_time=current_time
        )
        client.batch_write_base([base_item])
        
        # 创建analysis测试数据
        import hashlib
        item_id = hashlib.md5(base_item.title.encode('utf-8')).hexdigest()
        
        test_analysis = [{
            'item_id': item_id,
            'sentiment_score': 0.75,
            'type_name': '娱乐',
            'topic_name': '测试话题',
            'nlp_time': current_time
        }]
        
        print(f"准备写入 {len(test_analysis)} 条测试数据到analysis表")
        print(f"  item_id={item_id}")
        print(f"  数据类型: {type(test_analysis[0])}")
        
        count = client.batch_write_analysis(test_analysis)
        print(f"✓ analysis表写入结果: {count} 条")
        
        client.close()
        return count > 0
    except Exception as e:
        print(f"✗ analysis表写入失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_async_writer():
    """测试异步写入器"""
    print("\n" + "=" * 60)
    print("测试4: 异步写入器测试")
    print("=" * 60)
    
    try:
        writer = AsyncWriter(CONFIG['DB'], platform='weibo')
        writer.start()
        
        current_time = int(time.time())
        
        # 测试base队列
        print("入队base数据...")
        for i in range(3):
            item = HotSearchItem(
                rank=i+1,
                title=f"异步测试_{current_time}_{i}",
                url=f"https://weibo.com/async{i}",
                heat=500000,
                latest_crawl_time=current_time
            )
            result = writer.enqueue_base(item)
            print(f"  [{i}] enqueue_base: {result}, queue_size={writer.base_queue.qsize()}")
        
        # 测试analysis队列
        print("入队analysis数据...")
        import hashlib
        for i in range(3):
            analysis = {
                'item_id': hashlib.md5(f"异步测试_{current_time}_{i}".encode()).hexdigest(),
                'sentiment_score': 0.6,
                'type_name': '社会',
                'topic_name': f'异步话题{i}',
                'nlp_time': current_time
            }
            result = writer.enqueue_analysis(analysis)
            print(f"  [{i}] enqueue_analysis: {result}, queue_size={writer.analysis_queue.qsize()}")
        
        # 等待写入完成
        print("等待3秒让后台线程完成写入...")
        time.sleep(3)
        
        writer.stop()
        print("✓ 异步写入器测试完成")
        return True
    except Exception as e:
        print(f"✗ 异步写入器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_pipeline():
    """测试完整流程"""
    print("\n" + "=" * 60)
    print("测试5: 完整流程测试（模拟main.py流程）")
    print("=" * 60)
    
    try:
        from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
        from common.process.cleaner import Cleaner
        from common.process.llm_analyzer import LLMAnalyzer
        from common.storage.redis_manager import RedisManager
        
        # 初始化组件
        cleaner = Cleaner()
        analyzer = LLMAnalyzer(
            api_config=CONFIG['ANALYZER'],
            redis_config=CONFIG['REDIS']
        )
        redis = RedisManager(CONFIG['REDIS'])
        writer = AsyncWriter(CONFIG['DB'], platform='weibo')
        writer.start()
        
        # 1. 爬取数据
        print("\n[1/5] 爬取数据...")
        raw_items = get_realtime_data()
        if not raw_items:
            print("✗ 未爬取到数据")
            return False
        print(f"✓ 爬取到 {len(raw_items)} 条数据")
        
        # 检查数据类型
        print(f"  第一条数据类型: {type(raw_items[0])}")
        print(f"  title类型: {type(raw_items[0].title)}")
        print(f"  rank类型: {type(raw_items[0].rank)}")
        print(f"  heat类型: {type(raw_items[0].heat)}")
        print(f"  first_on_board_time类型: {type(raw_items[0].first_on_board_time)}")
        
        # 2. 清洗
        print("\n[2/5] 清洗数据...")
        items = cleaner.clean(raw_items)
        print(f"✓ 清洗后: {len(items)} 条")
        
        # 3. Redis缓存
        print("\n[3/5] Redis缓存...")
        redis.update_rank(items, 'weibo')
        redis.save_hot_search(items, 'weibo')
        print("✓ Redis缓存完成")
        
        # 4. LLM分析
        print("\n[4/5] LLM分析...")
        result = analyzer.process_items(items, CONFIG['REDIS'])
        all_processed = result['all_results']
        new_items = result['new_items']
        analysis_data = result['analysis_results']
        print(f"✓ 分析完成: 总计{len(all_processed)}条, 新增{len(new_items)}条")
        
        # 检查new_items类型
        if new_items:
            print(f"  new_items[0]类型: {type(new_items[0])}")
            print(f"  new_items[0].first_on_board_time: {new_items[0].first_on_board_time}")
        
        # 5. 异步写入MySQL
        print("\n[5/5] 异步写入MySQL...")
        
        # 5.1 写入base表
        base_count = 0
        for item in new_items:
            if writer.enqueue_base(item):
                base_count += 1
        print(f"  base表入队: {base_count} 条")
        
        # 5.2 写入analysis表
        analysis_items, _ = analyzer.get_items_for_db_write(analysis_data)
        analysis_count = 0
        for item in analysis_items:
            if writer.enqueue_analysis(item):
                analysis_count += 1
        print(f"  analysis表入队: {analysis_count} 条")
        
        # 等待写入
        print("  等待5秒完成后台写入...")
        time.sleep(5)
        
        # 停止writer
        writer.stop()
        redis.close()
        
        print("\n✓ 完整流程测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 完整流程测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "=" * 70)
    print(" MySQL写入全流程调试测试")
    print(" 时间:", datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("=" * 70)
    
    results = []
    
    # 运行测试
    results.append(("MySQL连接", test_mysql_connection()))
    results.append(("base表写入", test_batch_write_base()))
    results.append(("analysis表写入", test_batch_write_analysis()))
    results.append(("异步写入器", test_async_writer()))
    results.append(("完整流程", test_full_pipeline()))
    
    # 汇总结果
    print("\n" + "=" * 70)
    print("测试结果汇总")
    print("=" * 70)
    
    for name, passed in results:
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"  {name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\n总计: {passed}/{total} 通过")
    
    if passed == total:
        print("\n🎉 所有测试通过！MySQL写入功能正常。")
    else:
        print("\n⚠️  存在失败的测试，请检查上述日志定位问题。")


if __name__ == '__main__':
    main()
