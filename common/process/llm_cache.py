"""
模块名称: llm_cache.py
模块职责: LLM分析结果缓存管理（Redis）
"""
import json
import hashlib
from typing import Dict, Any, Optional
from common.utils.logging_config import logger


class LLMCache:
    CACHE_TTL = 86400
    
    def __init__(self, redis_config: Optional[Dict[str, Any]] = None):
        self.redis_client = None
        self._redis_config = None
        self.cache_hits = 0
        self.cache_misses = 0
        
        if redis_config:
            self._redis_config = redis_config
            self.init_redis(redis_config)
    
    def init_redis(self, redis_config: Dict[str, Any]) -> bool:
        try:
            import redis
            self._redis_config = redis_config
            self.redis_client = redis.Redis(
                host=redis_config.get('host', '127.0.0.1'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('db', 0),
                password=redis_config.get('password') or None,
                decode_responses=True
            )
            self.redis_client.ping()
            logger.info("LLM缓存Redis已启用")
            return True
        except Exception as e:
            logger.warning(f"LLM缓存Redis初始化失败: {e}")
            self.redis_client = None
            return False
    
    def _ensure_connection(self) -> bool:
        if self.redis_client is None:
            if self._redis_config:
                logger.warning("LLM缓存Redis客户端未初始化，尝试重新连接...")
                return self.init_redis(self._redis_config)
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            logger.warning("LLM缓存Redis连接已断开，尝试重新连接...")
            if self._redis_config:
                return self.init_redis(self._redis_config)
            return False

    def _get_cache_key(self, title: str) -> str:
        title_hash = hashlib.md5(title.encode('utf-8')).hexdigest()
        return f"llm:analysis:{title_hash}"
    
    def get(self, title: str) -> Optional[Dict[str, Any]]:
        if not self._ensure_connection():
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
        if not self._ensure_connection():
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
        self.cache_hits += 1
    
    def record_miss(self):
        self.cache_misses += 1
    
    def get_stats(self) -> tuple[int, int]:
        return self.cache_hits, self.cache_misses
    
    def get_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return self.cache_hits / total * 100
