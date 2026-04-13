"""
模块名称: redis_manager.py
模块职责: Redis缓存管理器，封装所有Redis操作
"""

import json
from typing import List, Dict, Any, Optional
import redis
from common.utils.logging_config import logger


class RedisManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self) -> bool:
        try:
            self.client = redis.Redis(
                host=self.config.get('host', '127.0.0.1'),
                port=self.config.get('port', 6379),
                db=self.config.get('db', 0),
                password=self.config.get('password') or None,
                decode_responses=True
            )
            self.client.ping()
            logger.info("Redis连接成功")
            return True
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self.client = None
            return False
    
    def _ensure_connection(self) -> bool:
        if self.client is None:
            logger.warning("Redis客户端未初始化，尝试重新连接...")
            return self._connect()
        try:
            self.client.ping()
            return True
        except Exception:
            logger.warning("Redis连接已断开，尝试重新连接...")
            return self._connect()

    def update_rank(self, items: List, platform: str = 'weibo') -> bool:
        if not self._ensure_connection():
            logger.warning("Redis未连接，跳过榜单更新")
            return False
        
        try:
            zset_key = f"{platform}:realtime_rank"
            pipeline = self.client.pipeline()
            pipeline.delete(zset_key)
            for item in items:
                pipeline.zadd(zset_key, {item.item_id: item.heat})
            pipeline.expire(zset_key, 600)
            pipeline.execute()
            logger.debug(f"Redis ZSet已更新: {len(items)} 条")
            return True
        except Exception as e:
            logger.error(f"更新Redis ZSet失败: {e}")
            return False
    
    def save_hot_search(self, items: List, platform: str = 'weibo') -> bool:
        if not self._ensure_connection():
            return False
        
        try:
            key_mapping = {
                'weibo': 'platform:weibo:realtime_board',
                'zhihu': 'platform:zhihu:realtime_board',
                'baidu': 'platform:baidu:realtime_board'
            }
            redis_key = key_mapping.get(platform, f'platform:{platform}:realtime_board')
            data = [item.to_dict(include_url=True, include_nlp=True) for item in items]
            json_str = json.dumps(data, ensure_ascii=False)
            self.client.setex(redis_key, 600, json_str)
            logger.debug(f"热搜数据已写入Redis: {redis_key}")
            return True
        except Exception as e:
            logger.error(f"保存热搜到Redis失败: {e}")
            return False
    
    def get_last_hot_search(self, platform: str = 'weibo') -> Optional[List[Dict]]:
        """获取上一轮热搜数据"""
        if not self._ensure_connection():
            return None
        
        try:
            key_mapping = {
                'weibo': 'platform:weibo:realtime_board',
                'zhihu': 'platform:zhihu:realtime_board',
                'baidu': 'platform:baidu:realtime_board'
            }
            redis_key = key_mapping.get(platform, f'platform:{platform}:realtime_board')
            data = self.client.get(redis_key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"获取上一轮热搜数据失败: {e}")
            return None
    
    def close(self):
        if self.client:
            self.client.close()
            logger.info("Redis连接已关闭")
