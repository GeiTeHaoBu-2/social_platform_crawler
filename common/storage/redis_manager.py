"""
模块名称: redis_manager.py
模块职责: Redis缓存管理器，封装所有Redis操作
输入接口: update_rank(items, platform)
输出格式: 无
依赖模块: redis
作者备注:
    - 封装Redis连接和操作
    - 支持ZSet榜单更新
    - 主流程只调用，不直接操作Redis
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
import redis
from common.utils.logging_config import logger


class RedisManager:
    """
    Redis缓存管理器
    
    职责:
    1. 管理Redis连接
    2. 更新ZSet实时榜单
    3. 保存热搜数据到Redis
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Redis管理器
        
        Args:
            config: Redis配置字典
        """
        self.config = config
        self.client: Optional[redis.Redis] = None
        self._connect()
    
    def _connect(self):
        """建立Redis连接"""
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
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self.client = None
    
    def update_rank(self, items: List, platform: str = 'weibo') -> bool:
        """
        更新Redis ZSet实时榜单
        
        Key: {platform}:realtime_rank
        Score: 热度值(heat)
        Member: item_id
        
        Args:
            items: HotSearchItem列表
            platform: 平台标识
            
        Returns:
            是否成功
        """
        if not self.client:
            logger.warning("Redis未连接，跳过榜单更新")
            return False
        
        try:
            zset_key = f"{platform}:realtime_rank"
            pipeline = self.client.pipeline()
            
            # 清空旧数据
            pipeline.delete(zset_key)
            
            # 添加新数据
            for item in items:
                item_id = hashlib.md5(item.title.encode('utf-8')).hexdigest()
                pipeline.zadd(zset_key, {item_id: item.heat})
            
            # 设置过期时间（10分钟）
            pipeline.expire(zset_key, 600)
            pipeline.execute()
            
            logger.debug(f"Redis ZSet已更新: {len(items)} 条")
            return True
            
        except Exception as e:
            logger.error(f"更新Redis ZSet失败: {e}")
            return False
    
    def save_hot_search(self, items: List, platform: str = 'weibo') -> bool:
        """
        保存热搜数据到Redis（兼容旧接口）
        
        Args:
            items: HotSearchItem列表
            platform: 平台标识
            
        Returns:
            是否成功
        """
        if not self.client:
            return False
        
        try:
            from common.models.item import HotSearchItem
            
            key_mapping = {
                'weibo': 'platform:weibo:realtime_board',
                'zhihu': 'platform:zhihu:realtime_board',
                'baidu': 'platform:baidu:realtime_board'
            }
            redis_key = key_mapping.get(platform, f'platform:{platform}:realtime_board')
            
            # 转换为字典列表
            data = [item.to_dict() for item in items]
            json_str = json.dumps(data, ensure_ascii=False)
            
            # 设置10分钟过期
            self.client.setex(redis_key, 600, json_str)
            logger.debug(f"热搜数据已写入Redis: {redis_key}")
            return True
            
        except Exception as e:
            logger.error(f"保存热搜到Redis失败: {e}")
            return False
    
    def close(self):
        """关闭Redis连接"""
        if self.client:
            self.client.close()
            logger.info("Redis连接已关闭")
