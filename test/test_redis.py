"""
Redis连接测试
"""
import sys
sys.path.insert(0, '.')

from common.storage.redis_manager import RedisManager
from common.config.settings import CONFIG


def test_redis():
    """测试Redis连接和操作"""
    print("=" * 50)
    print("Redis连接测试")
    print("=" * 50)
    
    try:
        # 1. 测试连接
        print("\n[1/3] 测试连接...")
        redis_mgr = RedisManager(CONFIG['REDIS'])
        
        if redis_mgr.client is None:
            print("✗ Redis连接失败")
            return False
        
        # 测试ping
        redis_mgr.client.ping()
        print("✓ Redis连接成功")
        
        # 2. 测试写入
        print("\n[2/3] 测试写入...")
        test_key = "test:connection"
        test_value = {"status": "ok", "test": True}
        
        import json
        redis_mgr.client.setex(test_key, 60, json.dumps(test_value, ensure_ascii=False))
        print(f"✓ 写入测试数据: {test_key}")
        
        # 3. 测试读取
        print("\n[3/3] 测试读取...")
        result = redis_mgr.client.get(test_key)
        if result:
            print(f"✓ 读取成功: {result}")
        else:
            print("✗ 读取失败")
            return False
        
        # 清理
        redis_mgr.client.delete(test_key)
        redis_mgr.close()
        
        print("\n" + "=" * 50)
        print("✓ Redis测试全部通过!")
        print("=" * 50)
        return True
        
    except Exception as e:
        print(f"✗ Redis测试失败: {e}")
        return False


if __name__ == "__main__":
    test_redis()
