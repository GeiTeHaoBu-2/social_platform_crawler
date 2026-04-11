"""
模块名称: dynamic_config.py
模块职责: 动态配置中心 - 支持运行时热更新LLM模型配置

命令行操作:
    redis-cli GET "config:llm:current"          # 查看当前模型
    redis-cli SET "config:llm:current" "backup_1"  # 切换模型
"""

import json
import time
import threading
from typing import Dict, Any, Optional, Callable
from common.utils.logging_config import logger


class DynamicConfigCenter:
    """
    动态配置中心 - 基于Redis实现配置热更新
    
    Redis Key:
    - config:llm:current        当前模型名称
    - config:llm:models:*       各模型配置
    - config:llm:version        配置版本号
    """
    
    KEY_CURRENT = "config:llm:current"
    KEY_VERSION = "config:llm:version"
    KEY_PREFIX = "config:llm:models"
    CHECK_INTERVAL = 5
    
    def __init__(self, redis_client, initial_config: Dict[str, Any],
                 on_config_change: Optional[Callable] = None):
        self.redis_client = redis_client
        self.initial_config = initial_config
        self.on_config_change = on_config_change
        self.current_model = 'primary'
        self.config_version = 0
        self.models_config = {}
        self._stop_event = threading.Event()
        self._watcher_thread = None
        self._init_redis_config()
        logger.info("动态配置中心初始化完成")
    
    def _init_redis_config(self):
        try:
            if not self.redis_client.exists(self.KEY_CURRENT):
                self._write_initial_config()
            else:
                self._load_config_from_redis()
        except Exception as e:
            logger.warning(f"Redis配置初始化失败: {e}")
            self._use_local_config()
    
    def _write_initial_config(self):
        pipe = self.redis_client.pipeline()
        pipe.set(self.KEY_CURRENT, 'primary')
        for name in ['primary', 'backup_1', 'backup_2']:
            if name in self.initial_config:
                cfg = self.initial_config[name]
                pipe.hset(f"{self.KEY_PREFIX}:{name}", mapping={
                    'api_url': cfg.get('api_url', ''),
                    'api_key': cfg.get('api_key', ''),
                    'model': cfg.get('model', ''),
                    'timeout': str(cfg.get('timeout', 30))
                })
        failover = self.initial_config.get('failover', {})
        pipe.hset("config:llm:failover", mapping={
            'max_retries': str(failover.get('max_retries', 2)),
            'auto_recover': str(failover.get('auto_recover', True))
        })
        pipe.set(self.KEY_VERSION, '1')
        pipe.execute()
        self.config_version = 1
        logger.info("初始配置已写入Redis")
    
    def _load_config_from_redis(self):
        current = self.redis_client.get(self.KEY_CURRENT)
        self.current_model = current if current else 'primary'
        version = self.redis_client.get(self.KEY_VERSION)
        self.config_version = int(version) if version else 0
        self.models_config = {}
        for name in ['primary', 'backup_1', 'backup_2']:
            key = f"{self.KEY_PREFIX}:{name}"
            if self.redis_client.exists(key):
                cfg = self.redis_client.hgetall(key)
                self.models_config[name] = {
                    'api_url': cfg.get('api_url', ''),
                    'api_key': cfg.get('api_key', ''),
                    'model': cfg.get('model', ''),
                    'timeout': int(cfg.get('timeout', 30))
                }
        logger.info(f"配置加载完成，当前模型: {self.current_model}")
    
    def _use_local_config(self):
        for name in ['primary', 'backup_1', 'backup_2']:
            if name in self.initial_config:
                self.models_config[name] = self.initial_config[name]
    
    def start_watching(self):
        if self._watcher_thread and self._watcher_thread.is_alive():
            return
        self._stop_event.clear()
        self._watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher_thread.start()
        logger.info("配置监听线程已启动")
    
    def stop_watching(self):
        self._stop_event.set()
        if self._watcher_thread:
            self._watcher_thread.join(timeout=2)
        logger.info("配置监听线程已停止")
    
    def _watch_loop(self):
        while not self._stop_event.is_set():
            try:
                self._check_config_change()
            except Exception as e:
                logger.error(f"配置检查异常: {e}")
            self._stop_event.wait(self.CHECK_INTERVAL)
    
    def _check_config_change(self):
        version = self.redis_client.get(self.KEY_VERSION)
        new_version = int(version) if version else 0
        if new_version != self.config_version:
            logger.info(f"检测到配置变化: {self.config_version} -> {new_version}")
            old_model = self.current_model
            self._load_config_from_redis()
            if self.current_model != old_model and self.on_config_change:
                self.on_config_change(self.current_model, self.get_current_config())
    
    def get_current_model(self) -> str:
        return self.current_model
    
    def get_current_config(self) -> Dict[str, Any]:
        return self.models_config.get(self.current_model, {})
    
    def get_all_configs(self) -> Dict[str, Any]:
        return {
            'current': self.current_model,
            'models': self.models_config,
            'version': self.config_version
        }
    
    def switch_model(self, model_name: str) -> bool:
        if model_name not in self.models_config:
            logger.error(f"模型 {model_name} 不存在")
            return False
        old_model = self.current_model
        self.current_model = model_name
        self.redis_client.set(self.KEY_CURRENT, model_name)
        new_version = self.config_version + 1
        self.redis_client.set(self.KEY_VERSION, str(new_version))
        self.config_version = new_version
        logger.info(f"模型切换: {old_model} -> {model_name}")
        return True
    
    def update_model_config(self, model_name: str, config: Dict[str, Any]) -> bool:
        if model_name not in ['primary', 'backup_1', 'backup_2']:
            return False
        key = f"{self.KEY_PREFIX}:{model_name}"
        self.redis_client.hset(key, mapping={
            'api_url': config.get('api_url', ''),
            'api_key': config.get('api_key', ''),
            'model': config.get('model', ''),
            'timeout': str(config.get('timeout', 30))
        })
        new_version = self.config_version + 1
        self.redis_client.set(self.KEY_VERSION, str(new_version))
        self.config_version = new_version
        logger.info(f"模型配置更新: {model_name}")
        return True
