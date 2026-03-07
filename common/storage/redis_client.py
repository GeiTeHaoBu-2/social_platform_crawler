import json
import redis
from typing import List
from common.models.item import HotSearchItem
from common.config.settings import REDIS_CONFIG
from common.utils.logging_config import logger

# ==========================================
# 1. 初始化全局 Redis 连接池
# ==========================================
try:
    redis_pool = redis.ConnectionPool(
        host=REDIS_CONFIG.get('host', '127.0.0.1'),
        port=REDIS_CONFIG.get('port', 6379),
        db=REDIS_CONFIG.get('data_db', 0),
        password=REDIS_CONFIG.get('password', None),
        decode_responses=True
    )
    redis_client = redis.Redis(connection_pool=redis_pool)
    logger.info("Redis 通用客户端连接池初始化成功！")
except Exception as e:
    logger.error(f"Redis 初始化失败: {e}")
    raise


# ==========================================
# 2. 核心通用写入方法
# ==========================================
def save_hot_search_to_redis(items: List[HotSearchItem], platform: str ):
    """
    通用保存方法：将指定平台的清洗榜单保存到 Redis。
    :param items: 标准化数据列表
    :param platform: 平台标识（默认 weibo），对应配置项中的 keys
    """
    if not items:
        return

    # 从配置中动态获取对应的 Redis Key
    keys_dict = REDIS_CONFIG.get('keys', {})
    board_key = keys_dict.get(platform)

    # 防御性编程：如果传了一个配置里没有的平台，果断拦截并报错
    if not board_key:
        logger.error(f"未在 REDIS_CONFIG 中找到平台 '{platform}' 的 Key 映射，保存中止！")
        return

    # 从配置读取过期时间，容错默认给 600 秒
    expire_time = REDIS_CONFIG.get('expire_time', 600)

    try:
        dict_items = [item.to_dict() for item in items]
        json_data = json.dumps(dict_items, ensure_ascii=False)

        # 动态使用指定的 Key 和过期时间
        redis_client.setex(board_key, expire_time, json_data)

        logger.debug(f"成功将 {len(items)} 条 [{platform}] 最新榜单刷新到 Redis！Key: {board_key}")
    except Exception as e:
        logger.error(f"保存 [{platform}] 实时榜单到 Redis 失败: {e}")