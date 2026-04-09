"""
模块名称: llm_cache.py
模块职责: LLM分析结果缓存管理（Redis）
"""
import json
import hashlib
from typing import Dict, Any, Optional
from common.utils.logging_config import logger


class LLMCache:
    """LLM分析结果缓存管理器"""
    
    # 缓存过期时间（秒）- 24小时
    CACHE_TTL = 86400
    
    def __init__(self, redis_config: Optional[Dict[str, Any]] = None):
        """
        初始化缓存管理器
        
        Args:
            redis_config: Redis配置字典
        """
        self.redis_client = None
        self.cache_hits = 0
        self.cache_misses = 0
        
        if redis_config:
            self.init_redis(redis_config)
    
    def init_redis(self, redis_config: Dict[str, Any]):
        """初始化Redis连接（公开方法）"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=redis_config.get('host', '127.0.0.1'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password') or None,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("LLM缓存Redis已启用")
        except Exception as e:
            logger.warning(f"LLM缓存Redis初始化失败: {e}")
            self.redis_client = None
    
    def _get_cache_key(self, title: str) -> str:
        """生成缓存key"""
        title_hash = hashlib.md5(title.encode('utf-8')).hexdigest()
        return f"llm:analysis:{title_hash}"
    
    def get(self, title: str) -> Optional[Dict[str, Any]]:
        """
        从缓存获取分析结果
        
        Args:
            title: 热搜标题
            
        Returns:
            缓存的分析结果或None
        """
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._get_cache_key(title)
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"缓存读取失败: {e}")
        
        return None
    
    def set(self, title: str, result: Dict[str, Any]):
        """
        保存分析结果到缓存
        
        Args:
            title: 热搜标题
            result: 分析结果字典
        """
        if not self.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(title)
            self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            logger.debug(f"缓存写入失败: {e}")
    
    def record_hit(self):
        """记录缓存命中"""
        self.cache_hits += 1
    
    def record_miss(self):
        """记录缓存未命中"""
        self.cache_misses += 1
    
    def get_stats(self) -> tuple[int, int]:
        """
        获取缓存统计
        
        Returns:
            (命中次数, 未命中次数)
        """
        return self.cache_hits, self.cache_misses
    
    def get_hit_rate(self) -> float:
        """
        获取缓存命中率
        
        Returns:
            命中率百分比
        """
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total * 100
