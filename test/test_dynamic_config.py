"""
测试动态配置中心功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import redis
from common.config.dynamic_config import DynamicConfigCenter
from common.config.settings import LLM_CONFIG, REDIS_CONFIG
from common.utils.logging_config import logger


def test_dynamic_config():
    """测试动态配置中心"""
    print("=" * 60)
    print("测试: 动态配置中心")
    print("=" * 60)
    
    # 连接Redis
    r = redis.Redis(
        host=REDIS_CONFIG.get('host', '127.0.0.1'),
        port=REDIS_CONFIG.get('port', 6379),
        db=REDIS_CONFIG.get('data_db', 0),
        decode_responses=True
    )
    
    # 清理测试数据
    print("\n1. 清理旧配置...")
    for key in r.scan_iter("config:llm:*"):
        r.delete(key)
    
    # 创建动态配置中心
    print("\n2. 初始化动态配置中心...")
    config_center = DynamicConfigCenter(
        redis_client=r,
        initial_config=LLM_CONFIG,
        on_config_change=lambda model, cfg: print(f"回调: 切换到 {model}")
    )
    
    # 查看初始状态
    print("\n3. 初始配置:")
    print(f"   当前模型: {config_center.get_current_model()}")
    print(f"   版本号: {config_center.config_version}")
    
    # 启动监听
    print("\n4. 启动配置监听...")
    config_center.start_watching()
    
    # 模拟外部修改Redis
    print("\n5. 模拟外部切换模型...")
    r.set("config:llm:current", "backup_1")
    r.set("config:llm:version", "2")
    
    # 等待监听线程检测
    time.sleep(6)
    print(f"   检测后当前模型: {config_center.get_current_model()}")
    
    # API方式切换
    print("\n6. 通过API切换模型...")
    config_center.switch_model("primary")
    print(f"   切换后当前模型: {config_center.get_current_model()}")
    
    # 更新模型配置
    print("\n7. 更新模型配置...")
    config_center.update_model_config("primary", {
        "api_url": "https://new-api.example.com/v1/chat",
        "api_key": "new-key",
        "model": "new-model",
        "timeout": 60
    })
    
    # 查看Redis中的配置
    print("\n8. Redis中的配置:")
    print(f"   current: {r.get('config:llm:current')}")
    primary_cfg = r.hgetall("config:llm:models:primary")
    print(f"   primary: {primary_cfg}")
    
    # 停止监听
    config_center.stop_watching()
    print("\n测试完成!")


def show_redis_commands():
    """显示常用Redis命令"""
    print("\n" + "=" * 60)
    print("常用 Redis 命令")
    print("=" * 60)
    print("""
# 查看当前模型
redis-cli GET "config:llm:current"

# 切换到 backup_1 模型
redis-cli SET "config:llm:current" "backup_1"
redis-cli INCR "config:llm:version"

# 切换回主模型
redis-cli SET "config:llm:current" "primary"
redis-cli INCR "config:llm:version"

# 查看主模型配置
redis-cli HGETALL "config:llm:models:primary"

# 更新主模型的model字段
redis-cli HSET "config:llm:models:primary" model "gpt-4"
redis-cli INCR "config:llm:version"

# 查看配置版本
redis-cli GET "config:llm:version"
""")


if __name__ == '__main__':
    test_dynamic_config()
    show_redis_commands()
