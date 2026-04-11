# 动态配置中心使用指南

## 📋 功能说明

无需重启 main 进程，即可动态切换 LLM 模型。

## 🏗️ 架构设计

```
┌─────────────────┐     ┌─────────────────┐
│   Redis         │ ←── │  配置监听线程    │
│  config:llm:*   │     │  (每5秒检查)     │
└─────────────────┘     └────────┬────────┘
                                 │ 发现变化
                                 ↓
                       ┌─────────────────┐
                       │   LLMClient     │
                       │  切换当前模型    │
                       └─────────────────┘
```

## 📝 Redis Key 设计

| Key | 类型 | 说明 |
|-----|------|------|
| `config:llm:current` | String | 当前使用的模型名称 |
| `config:llm:version` | String | 配置版本号（用于检测变化） |
| `config:llm:models:primary` | Hash | 主模型配置 |
| `config:llm:models:backup_1` | Hash | 备选模型1配置 |
| `config:llm:models:backup_2` | Hash | 备选模型2配置 |

## 🚀 使用方式

### 方式一：命令行操作 Redis

```bash
# 查看当前模型
redis-cli GET "config:llm:current"

# 切换到 backup_1 模型
redis-cli SET "config:llm:current" "backup_1"
redis-cli INCR "config:llm:version"

# 切换回主模型
redis-cli SET "config:llm:current" "primary"
redis-cli INCR "config:llm:version"

# 更新模型参数
redis-cli HSET "config:llm:models:primary" model "gpt-4-turbo"
redis-cli INCR "config:llm:version"

# 查看完整配置
redis-cli HGETALL "config:llm:models:primary"
```

### 方式二：Python API

```python
from common.config.dynamic_config import DynamicConfigCenter

# 初始化
config_center = DynamicConfigCenter(
    redis_client=redis_client,
    initial_config=LLM_CONFIG,
    on_config_change=lambda model, cfg: print(f"切换到 {model}")
)

# 启动监听（后台线程每5秒检查一次）
config_center.start_watching()

# 切换模型
config_center.switch_model("backup_1")

# 更新模型配置
config_center.update_model_config("primary", {
    "api_url": "https://api.openai.com/v1/chat/completions",
    "api_key": "sk-xxx",
    "model": "gpt-4",
    "timeout": 60
})

# 获取当前配置
current = config_center.get_current_config()
```

### 方式三：集成到 main.py

```python
# main.py 中集成
from common.config.dynamic_config import DynamicConfigCenter

class HotSearchPipeline:
    def __init__(self):
        # ... 其他初始化 ...
        
        # 创建动态配置中心
        self.config_center = DynamicConfigCenter(
            redis_client=self.redis.client,
            initial_config=CONFIG['ANALYZER'],
            on_config_change=self._on_llm_config_change
        )
        
        # 启动配置监听
        self.config_center.start_watching()
    
    def _on_llm_config_change(self, model_name: str, config: dict):
        """配置变化回调"""
        logger.info(f"🔄 LLM配置变化: 切换到 {model_name}")
        # 更新 LLMClient 的配置
        self.analyzer.client.update_model(model_name, config)
    
    def stop(self):
        self.config_center.stop_watching()
        # ... 其他清理 ...
```

## 📊 工作流程

1. **启动时**: 从 Redis 加载配置，如果不存在则写入初始配置
2. **运行时**: 后台线程每 5 秒检查 `config:llm:version`
3. **发现变化**: 重新加载配置，触发回调函数
4. **切换模型**: LLMClient 使用新配置

## ⚠️ 注意事项

1. **版本号递增**: 每次修改配置后必须 `INCR config:llm:version`
2. **线程安全**: 配置变化通过回调通知，在主线程处理
3. **回退机制**: Redis 连接失败时使用本地配置

## 🧪 测试

```bash
python test/test_dynamic_config.py
```
