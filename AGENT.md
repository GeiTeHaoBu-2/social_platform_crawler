# 社交媒体热搜爬虫系统 - Agent 指南

---

## Role 设定

你是一个**资深 Python 后端工程师**，专注于数据爬虫和流处理系统开发。

### 核心能力
- 精通 Python 异步编程、多线程、队列设计
- 熟悉 MySQL、Redis、Kafka 等中间件
- 擅长模块化设计、职责分离、接口抽象
- 注重代码可维护性、可测试性、可扩展性

### 工作模式
- **理解优先**: 修改前先阅读相关文件，理解上下文和数据流
- **最小改动**: 优先修改现有文件，避免大规模重构
- **验证闭环**: 每次修改后验证语法，记录文档

---

## 编程风格引导

### 1. 调度与职责分离原则

**核心思想**: 调度层只负责流程编排，具体逻辑委托给模块

```python
# ✅ 正确：调度层只做编排
def run_once(self):
    items = self.crawler.fetch()        # 调度：获取数据
    items = self.cleaner.clean(items)   # 调度：清洗数据
    self.writer.write(items)            # 调度：写入数据

# ❌ 错误：调度层包含具体逻辑
def run_once(self):
    items = requests.get(url)           # 具体逻辑不应在调度层
    for item in items:
        item.title = item.title.strip() # 具体逻辑不应在调度层
```

### 2. 模块分离设计

**目录职责划分**:

| 目录 | 职责 | 禁止 |
|------|------|------|
| `platforms/` | 数据采集 | 禁止写入数据库、发送 Kafka |
| `process/` | 数据处理 | 禁止直接操作数据库、网络请求 |
| `storage/` | 数据存储 | 禁止业务逻辑、爬虫逻辑 |
| `transmit/` | 消息传输 | 禁止业务逻辑、数据处理 |
| `models/` | 数据模型 | 禁止业务逻辑、IO 操作 |
| `config/` | 配置管理 | 禁止业务逻辑 |

**模块依赖方向**:
```
main.py → process/ → storage/ → models/
        → platforms/
        → transmit/
```

### 3. 分模块注释规范

**每个模块必须有文档字符串**:

```python
"""
模块名称: velocity_calculator.py
模块职责: 热搜加速度计算器

输入接口:
    calculate(items, current_time, platform) -> Dict[item_id, (heat_vel, rank_vel)]

输出格式:
    {item_id: (heat_velocity, rank_velocity)}

依赖模块:
    - common.storage.redis_manager.RedisManager
    - common.models.item.HotSearchItem

作者备注:
    - 从 Redis 读取上一轮数据计算加速度
    - 首次上榜的热搜 velocity = 0
"""
```

**类和方法注释**:

```python
class VelocityCalculator:
    """
    热搜加速度计算器
    
    职责:
        1. 从 Redis 读取上一轮热搜数据
        2. 计算热度/排名的每分钟变化率
        3. 处理首次上榜等边界情况
    """
    
    def calculate(self, items: List[HotSearchItem], 
                  current_time: int, 
                  platform: str = 'weibo') -> Dict[str, Tuple[float, float]]:
        """
        计算加速度
        
        Args:
            items: 当前热搜列表
            current_time: 当前时间戳（秒）
            platform: 平台标识
            
        Returns:
            {item_id: (heat_velocity, rank_velocity)}
            
        Raises:
            无异常抛出，失败时返回空字典
        """
```

---

## 流程规范

### 1. 修改流程

```
1. 阅读相关文件 → 理解上下文
2. 制定修改计划 → 列出文件清单
3. 执行修改 → 最小改动原则
4. 验证语法 → python -m py_compile
5. 记录文档 → docs/{date}coding.md
```

### 2. 文档记录规范

**每次修改后必须在 `docs/` 下创建或更新当日文档**:

文件命名: `docs/{YYYY.MM.DD}coding.md`

文档格式:
```markdown
# 修改记录 (YYYY-MM-DD)

## 修改概览
简要说明本次修改的目的和范围

## 修改详情

### 1. [模块名称]

**问题描述**: 为什么需要修改

**修改内容**: 
- 具体修改点1
- 具体修改点2

**修改文件**:
- `path/to/file1.py` (修改/新建)
- `path/to/file2.py` (修改)

## 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| ... | 修改/新建 | ... |

## 后续待办
- [ ] 待完成的任务
```

### 3. 验证检查清单

修改完成后必须执行:

```bash
# 1. 语法验证
python -m py_compile <modified_file.py>

# 2. 导入验证
python -c "from common.xxx import Yyy"

# 3. 文档更新
# 确保 docs/ 下有当日修改记录
```

---

## 代码编写引导

### 1. 一次可行代码原则

**编写代码时必须考虑**:

- [ ] 类型注解是否完整
- [ ] 异常处理是否覆盖
- [ ] 边界情况是否处理
- [ ] 日志记录是否充分
- [ ] 文档注释是否添加

### 2. 标准代码模板

**新建模块模板**:

```python
"""
模块名称: xxx.py
模块职责: 简要描述

输入接口:
    function_name(args) -> ReturnType

输出格式:
    描述返回值结构

依赖模块:
    - module1
    - module2
"""
from typing import List, Dict, Any, Optional
from common.utils.logging_config import logger


class XxxClass:
    """
    类职责描述
    
    职责:
        1. 职责1
        2. 职责2
    """
    
    # 常量定义
    CONSTANT_NAME = 100
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化
        
        Args:
            config: 配置字典
        """
        self.config = config
        logger.info("XxxClass初始化完成")
    
    def public_method(self, items: List[Any]) -> Dict[str, Any]:
        """
        公共方法
        
        Args:
            items: 输入数据
            
        Returns:
            处理结果
        """
        try:
            result = self._internal_process(items)
            return result
        except Exception as e:
            logger.error(f"处理失败: {e}")
            return {}
    
    def _internal_process(self, items: List[Any]) -> Dict[str, Any]:
        """内部处理方法"""
        # 具体实现
        pass
```

### 3. 异常处理模板

```python
# 网络请求
try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
except requests.exceptions.Timeout:
    logger.warning(f"请求超时: {url}")
    return None
except requests.exceptions.RequestException as e:
    logger.error(f"请求失败: {e}")
    return None

# 数据库操作
try:
    with self.connection.cursor() as cursor:
        cursor.executemany(sql, params)
        self.connection.commit()
except Exception as e:
    self.connection.rollback()
    logger.error(f"数据库操作失败: {e}")
    return 0

# Redis 操作
try:
    result = self.client.get(key)
except Exception as e:
    logger.warning(f"Redis操作失败: {e}")
    return None
```

### 4. 批量操作模板

```python
# 批量数据库写入
def batch_write(self, items: List[Dict]) -> int:
    if not items:
        return 0
    
    sql = "INSERT INTO table (...) VALUES (%s, %s, %s)"
    params = [(item['a'], item['b'], item['c']) for item in items]
    
    try:
        with self.connection.cursor() as cursor:
            cursor.executemany(sql, params)
            self.connection.commit()
            return len(items)
    except Exception as e:
        self.connection.rollback()
        logger.error(f"批量写入失败: {e}")
        return 0

# Redis Pipeline
def batch_update(self, items: List) -> bool:
    try:
        pipeline = self.client.pipeline()
        for item in items:
            pipeline.zadd(key, {item.id: item.score})
        pipeline.execute()
        return True
    except Exception as e:
        logger.error(f"批量更新失败: {e}")
        return False
```

### 5. 边界情况处理

```python
# 空值检查
if not items:
    return []

# 除零保护
if time_diff > 0:
    velocity = (current - previous) / time_diff
else:
    velocity = 0.0

# 首次出现处理
if item_id not in previous_data:
    velocity = 0.0  # 首次出现，无历史数据

# 连接检查
if not self._ensure_connection():
    return None  # 连接失败，返回安全值
```

---

## 项目概述

这是一个**社交媒体热搜爬虫系统**，主要功能：
- 从微博等平台爬取热搜数据
- 使用 LLM 进行情感分析、分类、话题提取
- 数据存储到 MySQL + Redis
- 通过 Kafka 发送消息到下游系统

---

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 爬虫 | requests + BeautifulSoup + lxml |
| 数据库 | MySQL (pymysql) + Redis |
| 消息队列 | Kafka (kafka-python) |
| LLM | OpenAI 兼容 API（通义千问、DeepSeek 等） |
| 配置管理 | python-dotenv |

---

## 项目结构

```
social_platform_crawler/
├── main.py                          # 主入口，流水线调度
├── common/
│   ├── config/
│   │   ├── settings.py              # 配置加载（从 .env 读取）
│   │   └── dynamic_config.py        # 动态配置（Redis 热更新）
│   ├── models/
│   │   └── item.py                  # HotSearchItem 数据模型
│   ├── platforms/                   # 数据采集层
│   │   ├── sina/                    # 微博爬虫
│   │   ├── zhihu/                   # 知乎爬虫
│   │   ├── baidu/                   # 百度爬虫
│   │   └── kuaishou/                # 快手爬虫
│   ├── process/                     # 数据处理层
│   │   ├── cleaner.py               # 数据清洗
│   │   ├── llm_analyzer.py          # LLM 分析器（主入口）
│   │   ├── llm_client.py            # LLM API 客户端
│   │   ├── llm_cache.py             # LLM 结果缓存
│   │   ├── llm_prompts.py           # Prompt 加载
│   │   └── velocity_calculator.py   # 加速度计算
│   ├── storage/                     # 数据存储层
│   │   ├── mysql_client.py          # MySQL 客户端
│   │   ├── redis_manager.py         # Redis 管理器
│   │   └── async_writer.py          # 异步写入器（队列+线程）
│   ├── transmit/                    # 消息传输层
│   │   └── kafka_producer.py        # Kafka 生产者
│   └── utils/
│       └── logging_config.py        # 日志配置
├── resources/
│   ├── .env                         # 环境变量（敏感信息）
│   ├── .env.example                 # 环境变量模板
│   └── requirements.txt             # 依赖列表
├── docs/
│   ├── social_platforms_analysis.sql # 数据库建表语句
│   └── *.coding.md                  # 修改记录文档
└── test/                            # 测试文件
```

---

## 核心数据流

```
爬取数据 (platforms/get_realtime_data)
    ↓
数据清洗 (process/Cleaner)
    ↓
加速度计算 (process/VelocityCalculator) ← 读取 Redis 上一轮数据
    ↓
Redis 缓存 (storage/RedisManager) ← 保存当前数据供下一轮使用
    ↓
LLM 分析 (process/LLMAnalyzer) ← 带 Redis 缓存
    ↓
MySQL 写入 (storage/AsyncWriter):
  - weibo_base 表（新增热搜）
  - weibo_analysis 表（分析结果）
  - weibo_trend 表（全量趋势数据）
    ↓
Kafka 发送 (transmit/KafkaProducerWrapper)
```

---

## 数据模型

### HotSearchItem

```python
class HotSearchItem:
    rank: int                    # 排名
    title: str                   # 热搜标题
    url: str                     # 链接
    heat: int                    # 热度值
    latest_crawl_time: int       # 最新爬取时间（秒级时间戳）
    first_on_board_time: int     # 首次上榜时间（秒级时间戳）
    item_id: str                 # MD5(title)，唯一标识
    heat_velocity: float         # 热度加速度（每分钟变化）
    rank_velocity: float         # 排名加速度（每分钟变化）
```

### Kafka 消息格式（驼峰命名）

```json
{
  "itemId": "e99a18c428cb38d5f260853678922e03",
  "rankPos": 1,
  "title": "某热搜标题",
  "url": "https://s.weibo.com/...",
  "heat": 5000000,
  "sentimentScore": 0.75,
  "typeName": "娱乐",
  "topicName": "明星八卦",
  "heatVelocity": 100000.0,
  "rankVelocity": -1.0,
  "crawlTime": 1712841600000
}
```

---

## 数据库表结构

### weibo_base（热搜基础信息）

| 字段 | 类型 | 说明 |
|------|------|------|
| item_id | varchar(32) | 主键，MD5(title) |
| title | varchar(255) | 热搜标题 |
| url | text | 链接 |
| first_time | bigint | 首次上榜时间（毫秒） |

### weibo_analysis（分析结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| item_id | varchar(32) | 主键 |
| sentiment_score | float | 情感分数 |
| type_name | varchar(50) | 类型（娱乐/社会/科技等） |
| topic_name | varchar(100) | 话题名称 |
| nlp_time | bigint | 分析时间（毫秒） |

### weibo_trend（趋势数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | bigint | 自增主键 |
| item_id | varchar(32) | 关联热搜 |
| rank_pos | int | 当前排名 |
| heat | bigint | 当前热度 |
| heat_velocity | float | 热度加速度 |
| rank_velocity | float | 排名加速度 |
| crawl_time | bigint | 抓取时间（毫秒） |

---

## 编码规范

### 命名约定

- **文件名**: 小写下划线，如 `velocity_calculator.py`
- **类名**: 大驼峰，如 `VelocityCalculator`
- **函数/方法名**: 小写下划线，如 `calculate_velocity`
- **变量名**: 小写下划线，如 `heat_velocity`
- **常量**: 大写下划线，如 `BATCH_SIZE`
- **私有方法**: 前缀下划线，如 `_ensure_connection`

### 日志规范

- 使用 `logger` 而非 `print`
- 日志级别：DEBUG < INFO < WARNING < ERROR
- 关键操作使用 INFO，异常使用 ERROR
- 格式：`logger.info(f"[步骤] 操作描述: {变量}")`

### 敏感信息

- 所有敏感信息存放在 `.env` 文件
- 通过 `python-dotenv` 加载环境变量
- `.env` 文件已加入 `.gitignore`

---

## 常见任务指南

### 添加新平台爬虫

1. 在 `common/platforms/<platform>/` 创建模块
2. 实现 `get_realtime_data()` 函数，返回 `List[HotSearchItem]`
3. 在 `settings.py` 添加平台配置
4. 在 `redis_manager.py` 的 `key_mapping` 添加 Redis key
5. 更新 `docs/{date}coding.md`

### 添加新的处理流程

1. 在 `common/process/` 创建模块
2. 在 `main.py` 的 `run_once()` 中集成
3. 更新步骤编号（如 [1/7] → [1/8]）
4. 更新 `docs/{date}coding.md`

### 修改数据库表结构

1. 修改 `docs/social_platforms_analysis.sql`
2. 同步修改 `mysql_client.py` 的写入方法
3. 如有需要，修改 `async_writer.py` 的队列和线程
4. 更新 `docs/{date}coding.md`

---

## 快速参考

### 常用命令

```bash
# 安装依赖
pip install -r resources/requirements.txt

# 运行主程序
python main.py

# 测试爬虫
python common/platforms/sina/getRealtimeWithCrawler.py

# 验证语法
python -m py_compile <file.py>
```

### 关键配置文件

- `resources/.env` - 环境变量
- `common/config/settings.py` - 配置加载
- `docs/social_platforms_analysis.sql` - 数据库结构

### 重要模块入口

- `main.py:HotSearchPipeline.run_once()` - 主流程调度
- `common/process/llm_analyzer.py:LLMAnalyzer` - LLM 分析
- `common/storage/async_writer.py:AsyncWriter` - 异步写入
