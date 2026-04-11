# LLM多模型故障转移功能实现总结

## 📋 功能概述
实现LLM API故障自动转移机制：当主模型连续失败2次后，自动切换到备选模型。

## 🔧 配置说明

### settings.py 配置示例
```python
LLM_CONFIG = {
    # 主模型配置（默认使用）
    'primary': {
        'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
        'api_key': 'your_primary_key',
        'model': 'tongyi-xiaomi-analysis-flash',
        'timeout': 30,
    },
    
    # 备选模型1（主模型连续失败2次后切换）
    'backup_1': {
        'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
        'api_key': 'your_backup1_key',
        'model': 'Pro/deepseek-ai/DeepSeek-R1',
        'timeout': 30,
    },
    
    # 备选模型2（备选1也失败时切换）
    'backup_2': {
        'api_url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
        'api_key': 'your_backup2_key',
        'model': 'glm-4-flash',
        'timeout': 30,
    },
    
    # 故障转移配置
    'failover': {
        'max_retries': 2,      # 连续失败多少次后切换
        'auto_recover': True,  # 下一个周期是否自动回退主模型
    },
    
    'enabled': True,
    'batch_size': 10
}
```

## 📝 修改文件列表

| 文件 | 修改内容 |
|------|----------|
| [`common/config/settings.py`](common/config/settings.py) | 添加多模型配置结构 |
| [`common/config/settings.example.py`](common/config/settings.example.py) | 更新配置示例 |
| [`common/process/llm_client.py`](common/process/llm_client.py) | **核心**: 实现故障转移逻辑 |
| [`common/process/llm_analyzer.py`](common/process/llm_analyzer.py) | 适配新配置格式 |
| [`test/test_llm_failover.py`](test/test_llm_failover.py) | 新增测试脚本 |

## 🎯 故障转移流程

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM请求流程                               │
├─────────────────────────────────────────────────────────────┤
│  1. 尝试使用主模型 (primary)                                  │
│     └── 成功 → 返回结果                                      │
│     └── 失败 → 失败计数+1                                    │
│                                                                │
│  2. 检查失败次数                                               │
│     └── 失败次数 < max_retries → 等待1秒重试                 │
│     └── 失败次数 >= max_retries → 切换到backup_1             │
│                                                                │
│  3. 使用backup_1                                              │
│     └── 成功 → 返回结果，下次请求尝试回退primary              │
│     └── 失败 → 继续失败计数                                  │
│                                                                │
│  4. 再次检查失败次数                                          │
│     └── 失败次数 >= max_retries → 切换到backup_2             │
│                                                                │
│  5. 使用backup_2                                              │
│     └── 成功 → 返回结果                                      │
│     └── 失败 → 所有模型失败，返回None                        │
└─────────────────────────────────────────────────────────────┘
```

## 📢 Logger提示示例

### 初始化日志
```
[INFO] - 🤖 LLM Client初始化完成
[INFO] -    主模型: tongyi-xiaomi-analysis-flash
[INFO] -    备选模型1: Pro/deepseek-ai/DeepSeek-R1
[INFO] -    备选模型2: glm-4-flash
[INFO] -    故障转移: 连续失败2次后切换
```

### 故障转移日志
```
[WARNING] - ⚠️  [LLM失败] primary 连续失败 1/2 次
[WARNING] - ⚠️  [LLM失败] primary 连续失败 2/2 次
[WARNING] - 🔄 [LLM模型切换] primary -> backup_1
[WARNING] -    原因: 连续失败2次
[WARNING] -    新模型: Pro/deepseek-ai/DeepSeek-R1
```

### Token耗尽日志
```
[WARNING] - ⚠️  [LLM限流] primary Token耗尽或请求过频 (429)
```

### 自动恢复日志
```
[INFO] - 🔄 [LLM自动恢复] 尝试回退到主模型...
[INFO] - ✅ [LLM自动恢复] 已切换回主模型: tongyi-xiaomi-analysis-flash
```

## 🧪 测试方法

```bash
# 测试故障转移功能（使用无效key模拟失败）
python test/test_llm_failover.py

# 使用真实配置测试
python test/test_llm_failover.py --real
```

## 🎨 支持的API格式

所有OpenAI兼容格式的API都支持：
- 通义千问 (阿里云)
- DeepSeek (SiliconFlow)
- 智谱AI (GLM)
- OpenAI
- Azure OpenAI
- 其他兼容OpenAI格式的API

## ⚙️ 自定义配置

### 调整故障转移阈值
```python
'failover': {
    'max_retries': 3,  # 改为3次后再切换
    'auto_recover': False,  # 禁用自动恢复
}
```

### 只配置一个备选
```python
LLM_CONFIG = {
    'primary': {...},
    'backup_1': {...},
    # backup_2 可选
}
```

## 🔒 注意事项

1. **API密钥安全**: 已将 `settings.py` 加入 `.gitignore`，不会提交到git
2. **网络超时**: 每个模型可配置不同的 `timeout`
3. **限流处理**: 429状态码会触发模型切换
4. **自动恢复**: 每个新请求周期会尝试回退到主模型（可配置）
