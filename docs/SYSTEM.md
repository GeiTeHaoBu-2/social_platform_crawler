# 社交媒体热搜分析系统 - 系统设计文档

## 一、系统概述

### 1.1 项目背景

随着社交媒体的快速发展，微博、知乎等平台的热搜榜单已成为公众获取热点信息的重要渠道。热搜数据具有实时性强、传播速度快、影响力大等特点，对其进行实时监控和分析具有重要的研究价值和应用前景。

### 1.2 系统目标

本系统旨在构建一个**实时社交媒体热搜监控与分析平台**，实现以下目标：

1. **多平台数据采集**：支持微博、知乎、百度等多个平台的热搜数据实时爬取
2. **智能内容分析**：利用大语言模型（LLM）对热搜内容进行情感分析、类型分类、话题提取
3. **趋势变化追踪**：计算热搜热度/排名的差值，追踪热点演变趋势
4. **实时数据分发**：通过消息队列将数据实时推送至下游分析系统
5. **可视化展示**：为前端提供结构化数据接口，支持数据可视化展示

### 1.3 系统定位

本系统定位为**数据采集与预处理层**，在整体架构中承担数据源的角色，为下游的实时计算、数据仓库、可视化展示等系统提供高质量的结构化数据。

---

## 二、系统架构设计

### 2.1 整体架构

系统采用**分层架构 + 流水线处理**的设计模式，分为以下层次：

```
┌─────────────────────────────────────────────────────────────┐
│                      调度层 (main.py)                        │
│                   流程编排、任务调度                          │
├─────────────────────────────────────────────────────────────┤
│  采集层        │  处理层        │  存储层      │  传输层     │
│ (platforms/)   │ (process/)     │ (storage/)   │(transmit/) │
│                │                │              │            │
│ - 微博爬虫     │ - 数据清洗     │ - MySQL      │ - Kafka    │
│ - 知乎爬虫     │ - LLM分析      │ - Redis      │            │
│ - 百度爬虫     │ - 差值计算   │              │            │
└─────────────────────────────────────────────────────────────┘
├─────────────────────────────────────────────────────────────┤
│                      基础设施层                              │
│           配置管理、日志系统、数据模型                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 核心设计原则

#### 2.2.1 调度与职责分离

**设计思想**：调度层只负责流程编排，具体业务逻辑委托给各功能模块。

**实现方式**：
- `main.py` 中的 `HotSearchPipeline` 类作为调度器
- 各模块通过接口方法被调度器调用
- 模块之间无直接依赖，通过数据对象传递信息

```python
# 调度层示例
def run_once(self):
    items = self.crawler.fetch()           # 调度：获取数据
    items = self.cleaner.clean(items)      # 调度：清洗数据
    velocity = self.calculator.calculate() # 调度：计算差值
    self.writer.write(items)               # 调度：写入数据
```

#### 2.2.2 模块化设计

**设计思想**：按功能职责划分模块，高内聚低耦合。

| 模块目录 | 职责 | 核心类/函数 |
|---------|------|------------|
| `platforms/` | 数据采集 | `get_realtime_data()` |
| `process/` | 数据处理 | `Cleaner`, `LLMAnalyzer`, `DiffCalculator` |
| `storage/` | 数据存储 | `MySQLClient`, `RedisManager`, `AsyncWriter` |
| `transmit/` | 消息传输 | `KafkaProducerWrapper` |
| `models/` | 数据模型 | `HotSearchItem` |
| `config/` | 配置管理 | `settings.py`, `DynamicConfigCenter` |

#### 2.2.3 异步处理设计

**设计思想**：将耗时操作（数据库写入）异步化，避免阻塞主流程。

**实现方式**：
- 使用 `queue.Queue` 作为缓冲队列
- 使用 `threading.Thread` 创建后台守护线程
- 批量写入策略：满100条或每5秒强制刷盘

```
主线程                          后台线程
   │                               │
   │  enqueue(item)                │
   ├──────────────────────────────►│
   │                               ├── 批量写入MySQL
   │  继续处理                      │
   │                               │
```

---

## 三、技术选型

### 3.1 技术栈总览

| 类别 | 技术选型 | 版本要求 | 选型理由 |
|------|---------|---------|---------|
| 编程语言 | Python | 3.10+ | 丰富的数据处理库、简洁的语法、快速开发 |
| HTTP请求 | requests | 2.28+ | 简单易用、功能完善、社区活跃 |
| HTML解析 | BeautifulSoup + lxml | 4.12+ / 4.9+ | 解析速度快、容错性强 |
| 关系数据库 | MySQL | 5.7+ | 成熟稳定、支持事务、生态完善 |
| 缓存数据库 | Redis | 4.0+ | 高性能、支持多种数据结构 |
| 消息队列 | Kafka | 2.0+ | 高吞吐、持久化、支持流处理 |
| LLM接口 | OpenAI兼容API | - | 统一接口、多模型支持 |
| 配置管理 | python-dotenv | 1.0+ | 环境变量管理、敏感信息隔离 |

### 3.2 核心技术详解

#### 3.2.1 数据采集技术

**爬虫策略**：
- 使用 `requests` 发送 HTTP 请求
- 使用 `BeautifulSoup` + `lxml` 解析 HTML
- 通过 Cookie 认证绕过登录限制
- 设置合理的请求间隔，避免被封禁

**反爬应对**：
- 携带完整的请求头（User-Agent、Referer、Cookie）
- Cookie 定期更新机制
- 请求失败时返回空列表，不中断程序

#### 3.2.2 LLM 分析技术

**模型选择**：
- 主模型：通义千问（tongyi-xiaomi-analysis-flash）
- 备选模型：DeepSeek-R1、GLM-4-flash
- 支持动态切换，实现故障转移

**Prompt 工程**：
```python
SYSTEM_PROMPT = """
你是一个热搜分析专家。请分析以下热搜标题，返回JSON格式：
{
    "sentiment_score": 0.5,  # 情感分数 -1到1
    "type_name": "娱乐",      # 类型分类
    "topic_name": "明星八卦"   # 话题提取
}
"""
```

**缓存策略**：
- 使用 Redis 缓存 LLM 分析结果
- 缓存 Key：`llm:analysis:{MD5(title)}`
- 缓存 TTL：24小时
- 命中率优化：相同标题直接返回缓存结果

#### 3.2.3 差值计算技术

**计算公式**：
```
heatDiff = (当前热度 - 上次热度) / 时间差(分钟)
rankDiff = (当前排名 - 上次排名) / 时间差(分钟)
```

**数据来源**：
- 当前数据：本轮爬取结果
- 历史数据：Redis 中存储的上一轮数据
- 存储位置：`platform:weibo:realtime_board`

**边界处理**：
| 场景 | 处理方式 |
|------|---------|
| 首次运行 | velocity = 0 |
| 热搜首次上榜 | velocity = 0 |
| 时间差 ≤ 0 | velocity = 0 |
| Redis 连接失败 | velocity = 0，继续执行 |

---

## 四、数据流设计

### 4.1 主流程数据流

```
┌──────────────┐
│  1. 数据采集  │  get_realtime_data()
│   platforms/ │  返回 List[HotSearchItem]
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  2. 数据清洗  │  Cleaner.clean()
│   process/   │  去除空白、格式化
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 3. 差值计算 │  DiffCalculator.calculate()
│   process/   │  读取Redis历史数据，计算velocity
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 4. Redis缓存 │  RedisManager.save_hot_search()
│   storage/   │  保存当前数据供下一轮使用
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  5. LLM分析  │  LLMAnalyzer.process_items()
│   process/   │  情感分析、分类、话题提取
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 6. MySQL写入 │  AsyncWriter (异步)
│   storage/   │  base表、analysis表、trend表
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 7. Kafka发送 │  KafkaProducerWrapper.send()
│  transmit/   │  推送至下游系统
└──────────────┘
```

### 4.2 数据对象流转

```python
# 数据对象在各模块间的流转
HotSearchItem(
    rank=1,
    title="某热搜",
    url="https://...",
    heat=5000000,
    latest_crawl_time=1712841600,
    first_on_board_time=1712841600,
    item_id="e99a18c4...",      # 自动生成
    heat_diff=100000.0,     # 差值计算后填充
    rank_diff=-1.0          # 差值计算后填充
)
    │
    ├─► LLM分析后添加：
    │   sentiment_score=0.75
    │   type_name="娱乐"
    │   topic_name="明星八卦"
    │
    └─► Kafka消息格式：
        {
            "itemId": "e99a18c4...",
            "rankPos": 1,
            "title": "某热搜",
            "heat": 5000000,
            "heatDiff": 500000,
            "rankDiff": -2,
            "sentimentScore": 0.75,
            "typeName": "娱乐",
            "topicName": "明星八卦",
            "crawlTime": 1712841600000
        }
```

---

## 五、数据库设计

### 5.1 数据库架构

系统采用**维度建模**思想，将数据分为维度表和事实表：

```
┌─────────────────────────────────────────────────────────┐
│                     维度表                               │
├─────────────────────┬───────────────────────────────────┤
│    weibo_base       │    weibo_analysis                 │
│  (热搜基础信息)      │    (分析结果)                     │
│                     │                                   │
│  item_id (PK)       │    item_id (PK)                   │
│  title              │    sentiment_score                │
│  url                │    type_name                      │
│  first_time         │    topic_name                     │
│                     │    nlp_time                       │
└─────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                     事实表                               │
├─────────────────────────────────────────────────────────┤
│                    weibo_trend                          │
│                  (趋势流水表)                            │
│                                                         │
│  id (PK, Auto Increment)                                │
│  item_id (FK)                                           │
│  rank_pos                                               │
│  heat                                                   │
│  heat_diff                                          │
│  rank_diff                                          │
│  crawl_time                                             │
│  process_time                                           │
└─────────────────────────────────────────────────────────┘
```

### 5.2 表结构详解

#### 5.2.1 weibo_base（热搜基础信息表）

**用途**：存储热搜的基础信息，首次上榜后不再更新。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| item_id | varchar(32) | PRIMARY KEY | MD5(title)，唯一标识 |
| title | varchar(255) | NOT NULL | 热搜标题 |
| url | text | | 跳转链接 |
| first_time | bigint | NOT NULL | 首次上榜时间（毫秒时间戳） |
| create_time | timestamp | DEFAULT CURRENT_TIMESTAMP | 入库时间 |

**设计要点**：
- 使用 `INSERT IGNORE` 避免重复插入
- `first_time` 字段记录首次出现时间，用于分析热搜生命周期

#### 5.2.2 weibo_analysis（分析结果表）

**用途**：存储 LLM 分析结果，支持更新。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| item_id | varchar(32) | PRIMARY KEY | 关联 weibo_base |
| sentiment_score | float | DEFAULT 0 | 情感分数 (-1 到 1) |
| type_name | varchar(50) | DEFAULT '未知' | 内容类型 |
| topic_name | varchar(100) | NOT NULL | 话题名称 |
| nlp_time | bigint | NOT NULL | 分析时间（毫秒） |
| update_time | timestamp | ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

**设计要点**：
- 使用 `ON DUPLICATE KEY UPDATE` 实现幂等写入
- 每次分析结果更新都会刷新 `update_time`

#### 5.2.3 weibo_trend（趋势流水表）

**用途**：记录每次爬取的热搜状态，用于趋势分析。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | bigint | PRIMARY KEY AUTO_INCREMENT | 流水主键 |
| item_id | varchar(32) | NOT NULL | 关联热搜 |
| rank_pos | int | NOT NULL | 当前排名 |
| heat | bigint | NOT NULL | 当前热度 |
| heat_diff | BIGINT | DEFAULT 0 | 热度差值 |
| rank_diff | INT | DEFAULT 0 | 排名差值 |
| crawl_time | bigint | NOT NULL | 抓取时间（毫秒） |
| process_time | timestamp | DEFAULT CURRENT_TIMESTAMP | 入库时间 |

**索引设计**：
- `idx_item_time(item_id, crawl_time)`：按热搜查询历史趋势
- `idx_crawl_time(crawl_time)`：按时间范围查询

---

## 六、核心模块实现

### 6.1 数据采集模块

#### 6.1.1 模块结构

```
common/platforms/
├── sina/                          # 微博平台
│   └── getRealtimeWithCrawler.py  # 爬虫实现
├── zhihu/                         # 知乎平台
├── baidu/                         # 百度平台
└── kuaishou/                      # 快手平台
```

#### 6.1.2 核心实现

```python
def get_realtime_data() -> List[HotSearchItem]:
    """
    微博热搜数据采集
    
    采集流程:
    1. 构造请求头（含Cookie认证）
    2. 发送HTTP请求获取页面
    3. 解析HTML提取热搜列表
    4. 封装为HotSearchItem对象列表
    
    Returns:
        List[HotSearchItem]: 热搜列表
    """
    # 请求配置
    url = "https://s.weibo.com/top/summary"
    headers = {
        "User-Agent": "...",
        "Cookie": os.getenv('WEIBO_COOKIE'),
        "Referer": "https://weibo.com/"
    }
    
    # 发送请求
    response = requests.get(url, headers=headers, timeout=10)
    
    # 解析页面
    soup = BeautifulSoup(response.text, 'lxml')
    items = []
    for row in soup.select('#pl_top_realtimehot tbody tr'):
        item = HotSearchItem(
            rank=extract_rank(row),
            title=extract_title(row),
            url=extract_url(row),
            heat=extract_heat(row),
            latest_crawl_time=int(time.time())
        )
        items.append(item)
    
    return items
```

### 6.2 LLM 分析模块

#### 6.2.1 模块结构

```
common/process/
├── llm_analyzer.py      # 分析器主入口
├── llm_client.py        # API客户端
├── llm_cache.py         # 结果缓存
├── llm_prompts.py       # Prompt管理
└── llm_topic_extractor.py  # 话题提取降级
```

#### 6.2.2 核心实现

```python
class LLMAnalyzer:
    """
    LLM分析器
    
    职责:
    1. 调用LLM API进行内容分析
    2. 管理分析结果缓存
    3. 支持多模型故障转移
    """
    
    def analyze(self, title: str) -> Dict[str, Any]:
        # 1. 检查缓存
        cached = self.cache.get(title)
        if cached:
            return cached
        
        # 2. 构造消息
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请分析：{title}"}
        ]
        
        # 3. 调用API
        response = self.client.chat(messages)
        result = self.client.parse_json_response(response)
        
        # 4. 缓存结果
        self.cache.set(title, result)
        
        return result
```

#### 6.2.3 故障转移机制

```python
class LLMClient:
    """
    LLM客户端 - 支持多模型故障转移
    
    模型优先级:
    1. primary (通义千问)
    2. backup_1 (DeepSeek)
    3. backup_2 (GLM-4)
    """
    
    def chat(self, messages: List[Dict]) -> str:
        for model_name in ['primary', 'backup_1', 'backup_2']:
            config = self.config.get(model_name)
            try:
                response = self._call_api(config, messages)
                return response
            except Exception as e:
                logger.warning(f"{model_name} 调用失败: {e}")
                continue
        
        raise Exception("所有模型调用失败")
```

### 6.3 异步写入模块

#### 6.3.1 架构设计

```
┌─────────────┐     enqueue()     ┌─────────────┐
│   主线程    │ ─────────────────►│    Queue    │
│  (爬虫)     │                   │  (缓冲队列)  │
└─────────────┘                   └──────┬──────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │  后台线程   │
                                  │ (批量写入)  │
                                  └──────┬──────┘
                                         │
                                         ▼
                                  ┌─────────────┐
                                  │   MySQL     │
                                  └─────────────┘
```

#### 6.3.2 核心实现

```python
class AsyncWriter:
    """
    异步写入器
    
    设计要点:
    1. 使用Queue解耦生产者和消费者
    2. 后台线程独立MySQL连接，避免线程安全问题
    3. 批量写入策略：100条或5秒
    """
    
    BATCH_SIZE = 100
    FLUSH_INTERVAL = 5
    
    def _writer_loop(self):
        """后台写入线程"""
        buffer = []
        last_flush = time.time()
        
        while True:
            # 从队列取数据
            try:
                item = self.queue.get(timeout=0.1)
                buffer.append(item)
            except queue.Empty:
                pass
            
            # 判断是否需要刷盘
            should_flush = (
                len(buffer) >= self.BATCH_SIZE or
                (buffer and time.time() - last_flush >= self.FLUSH_INTERVAL)
            )
            
            if should_flush and buffer:
                self._write_batch(buffer)
                buffer = []
                last_flush = time.time()
```

---

## 七、系统特色与创新点

### 7.1 技术创新

#### 7.1.1 热搜差值计算

**创新点**：首次将物理学中的"差值"概念引入热搜趋势分析。

**实现方式**：
- 实时计算热度/排名的变化率
- 单位：每分钟变化量
- 应用：识别快速上升/下降的热点

**应用价值**：
- 预测热搜走势
- 发现潜在爆点
- 辅助舆情监控

#### 7.1.2 LLM 智能分析

**创新点**：将大语言模型应用于热搜内容理解。

**分析维度**：
- 情感分析：判断热搜情感倾向
- 类型分类：自动归类（娱乐/社会/科技等）
- 话题提取：识别核心话题

**技术优势**：
- 无需训练模型，直接使用
- 支持多模型切换，保证可用性
- 结果缓存，降低成本

#### 7.1.3 动态配置中心

**创新点**：基于 Redis 实现配置热更新。

**实现方式**：
```python
# Redis Key设计
config:llm:current      # 当前模型名称
config:llm:models:*     # 各模型配置
config:llm:version      # 配置版本号

# 热更新流程
1. 修改Redis中的配置
2. 版本号+1
3. 各节点检测版本变化
4. 自动加载新配置
```

**应用场景**：
- LLM 模型切换
- API Key 更新
- 参数动态调整

### 7.2 架构优势

#### 7.2.1 高可用设计

| 故障场景 | 应对策略 |
|---------|---------|
| 爬虫失败 | 返回空列表，记录日志，不中断程序 |
| LLM调用失败 | 多模型故障转移，降级返回默认值 |
| Redis连接失败 | 自动重连机制，缓存功能降级 |
| MySQL写入失败 | 事务回滚，数据保留在队列 |
| Kafka发送失败 | 异步回调记录，统计失败数量 |

#### 7.2.2 高性能设计

| 性能瓶颈 | 优化方案 |
|---------|---------|
| 数据库写入 | 异步队列 + 批量写入 |
| Redis操作 | Pipeline批量执行 |
| LLM调用 | 结果缓存 + 批量请求 |
| 网络请求 | 超时控制 + 连接复用 |

#### 7.2.3 可扩展设计

**水平扩展**：
- 多实例部署，共享 Redis/Kafka
- 每个实例独立爬取，通过 Kafka 去重

**垂直扩展**：
- 新增平台：在 `platforms/` 添加模块
- 新增分析：在 `process/` 添加模块
- 新增存储：在 `storage/` 添加队列和线程

---

## 八、部署与运维

### 8.1 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.10+ | 类型注解支持 |
| MySQL | 5.7+ | 事务支持 |
| Redis | 4.0+ | 数据结构支持 |
| Kafka | 2.0+ | 消息队列 |

### 8.2 配置管理

**环境变量配置** (`resources/.env`)：
```bash
# 数据库配置
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=social_platforms_analysis

# Redis配置
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# Kafka配置
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
KAFKA_TOPIC=weibo.hotsearch

# LLM配置
LLM_PRIMARY_API_URL=https://api.openai.com/v1/chat/completions
LLM_PRIMARY_API_KEY=your_api_key
LLM_PRIMARY_MODEL=gpt-3.5-turbo

# 微博Cookie
WEIBO_COOKIE=your_cookie
```

### 8.3 启动方式

```bash
# 安装依赖
pip install -r resources/requirements.txt

# 启动主程序
python main.py

# 后台运行
nohup python main.py > logs/crawler.log 2>&1 &
```

---

## 九、总结与展望

### 9.1 系统总结

本系统实现了一个完整的社交媒体热搜监控与分析平台，具有以下特点：

1. **架构清晰**：分层设计、模块化实现、职责分离
2. **技术先进**：LLM智能分析、差值趋势追踪、动态配置
3. **性能优异**：异步处理、批量操作、缓存优化
4. **稳定可靠**：故障转移、自动重连、优雅降级

### 9.2 未来展望

| 方向 | 规划 |
|------|------|
| 平台扩展 | 支持抖音、小红书等更多平台 |
| 分析深化 | 增加关键词提取、摘要生成、舆情预警 |
| 实时计算 | 集成 Flink 进行实时流处理 |
| 可视化 | 开发 Web 前端，实现数据可视化 |
| 机器学习 | 训练专用模型，提升分析准确率 |

---

## 附录

### A. 项目目录结构

```
social_platform_crawler/
├── main.py                          # 主入口
├── common/
│   ├── config/
│   │   ├── settings.py              # 配置加载
│   │   └── dynamic_config.py        # 动态配置
│   ├── models/
│   │   └── item.py                  # 数据模型
│   ├── platforms/
│   │   ├── sina/                    # 微博爬虫
│   │   ├── zhihu/                   # 知乎爬虫
│   │   ├── baidu/                   # 百度爬虫
│   │   └── kuaishou/                # 快手爬虫
│   ├── process/
│   │   ├── cleaner.py               # 数据清洗
│   │   ├── llm_analyzer.py          # LLM分析
│   │   ├── llm_client.py            # API客户端
│   │   ├── llm_cache.py             # 结果缓存
│   │   ├── llm_prompts.py           # Prompt管理
│   │   └── diff_calculator.py   # 差值计算
│   ├── storage/
│   │   ├── mysql_client.py          # MySQL客户端
│   │   ├── redis_manager.py         # Redis管理
│   │   └── async_writer.py          # 异步写入
│   ├── transmit/
│   │   └── kafka_producer.py        # Kafka生产者
│   └── utils/
│       └── logging_config.py        # 日志配置
├── resources/
│   ├── .env                         # 环境变量
│   ├── .env.example                 # 环境变量模板
│   └── requirements.txt             # 依赖列表
├── docs/
│   ├── social_platforms_analysis.sql # 数据库建表
│   └── *.coding.md                  # 修改记录
├── AGENT.md                         # Agent指南
└── SYSTEM.md                        # 系统设计文档
```

### B. 关键接口定义

```python
# 数据采集接口
def get_realtime_data() -> List[HotSearchItem]:
    """获取实时热搜数据"""

# 数据清洗接口
def clean(items: List[HotSearchItem]) -> List[HotSearchItem]:
    """清洗热搜数据"""

# 差值计算接口
def calculate(items: List[HotSearchItem], current_time: int) -> Dict[str, Tuple[float, float]]:
    """计算热搜差值"""

# LLM分析接口
def analyze(title: str) -> Dict[str, Any]:
    """分析热搜内容"""

# 数据写入接口
def enqueue_base(item: HotSearchItem) -> bool:
    """入队base表数据"""
def enqueue_analysis(item: Dict) -> bool:
    """入队analysis表数据"""
def enqueue_trend(item: Dict) -> bool:
    """入队trend表数据"""

# Kafka发送接口
def send(topic: str, message: Dict, key: str) -> None:
    """发送消息到Kafka"""
```

### C. 数据模型定义

```python
class HotSearchItem:
    """热搜数据模型"""
    rank: int                    # 排名
    title: str                   # 标题
    url: str                     # 链接
    heat: int                    # 热度
    latest_crawl_time: int       # 最新爬取时间（秒）
    first_on_board_time: int     # 首次上榜时间（秒）
    item_id: str                 # 唯一标识 MD5(title)
    heat_diff: int         # 热度差值
    rank_diff: int         # 排名差值
```
