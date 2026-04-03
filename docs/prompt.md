# Role
你是一位拥有 10 年经验的高级 Python 后端工程师，擅长高并发数据采集与 ETL 流程重构。你的风格是严谨、高效、零容忍架构违规。

# Context
我正在开发"社会热点舆情实时追踪系统"。
架构流程：Python (爬虫/ETL) -> Kafka -> Flink (计算) -> MySQL (存储)。

**当前项目结构**：
```
common/
├── main.py                    # 主流程入口，需重构为异步架构
├── config/settings.py         # 全局配置（需解耦注入）
├── models/item.py             # HotSearchItem 数据模型
├── platforms/
│   └── sina/
│       ├── getRealtimeWithCrawler.py   # 微博爬虫（BS4解析HTML）
│       └── getHotSearchWithApi.py      # API方式（备用）
├── process/
│   ├── cleaner.py             # 数据清洗 + 生成item_id(MD5)
│   ├── nlp_pipeline.py        # 新增：NLP分析 + Redis缓存判断
│   └── topic_clusterer.py     # 新增：话题聚类
├── storage/
│   ├── mysql_client.py        # 需改造为仅写入维度表+异步队列
│   └── redis_client.py        # 榜单缓存(ZSet) + NLP缓存
└── transmit/
    └── kafka_producer.py      # Kafka生产者（配置注入）
```

**⚠️ 重要删除**：`deduplicationer.py` 已删除，其逻辑并入 `nlp_pipeline.py`。
**⚠️ 严禁**：严禁基于排名/热度变化过滤 Kafka 消息。所有爬取到的热搜必须全量发送 Kafka。

**数据库 Schema（Critical Mapping）**：

| 表名 | 职责 | 写入方 |
|------|------|--------|
| `weibo_base` | 热搜基础信息（item_id, title, url, first_time） | **Python** |
| `weibo_analysis` | 分析结果（sentiment_score, topic_name, type_name, nlp_time） | **Python** |
| `weibo_trend` | 趋势流水（rank_pos, heat, crawl_time） | **Flink（Python禁止）** |
| `fact_topic_stats` | 话题统计结果 | **Flink** |
| `sys_user`/`user_login_log` | 系统用户表 | 爬虫不操作 |

**⚠️ 红线**：`weibo_trend` 表 **绝对禁止** Python 写入，已有 Flink 负责。

**当前已知问题**：
1. `mysql_client.py` 违规写入 `weibo_trend` 表，必须删除
2. `main.py` 是同步顺序执行，数据库写入阻塞主爬虫线程
3. 缺少 NLP 模块和异步写入队列
4. `getRealtimeWithCrawler.py` 第94行有非法的 `get_realtime_data()` 调用
5. 配置与业务代码耦合严重

---

# 业务流程（必须严格遵循）

## 完整执行流程

```
1. 加载配置
   └─> 从 settings.py 加载 DB、Redis、Kafka 配置

2. 初始化组件
   └─> 初始化连接池、Kafka Producer、异步 DB 队列线程

3. 调度爬虫
   └─> 主控制程序触发爬取任务

4. 爬取与清洗
   └─> 获取原始数据，清洗标题，生成 item_id = MD5(title)

5. 更新实时缓存 (Redis ZSet)
   └─> 使用 **ZSet** 数据结构写入 Redis
       - Key: `weibo:realtime_rank`
       - Score: 热度值 (heat) 或 排名 (rank_pos)
       - Member: item_id
       - 目的：支持前端按热度/排名排序查询
   ⚠️ 禁止写 MySQL 的 current 表（已废除）

6. NLP 缓存筛查
   └─> 查询 Redis `nlp_cache:{item_id}`
       ├─> 命中：直接读取 sentiment, topic_name, type_name
       └─> 未命中：
           ├─> 调用 NLP 分析
           ├─> 结果放入异步 DB 队列 (写 weibo_base + weibo_analysis)
           └─> 写入 Redis 缓存

7. 组装 Kafka 消息
   └─> 包含：item_id, title, rank_pos, heat, crawl_time, 
           sentiment_score, topic_name, type_name

8. 发送 Kafka
   └─> producer.send(topic='weibo_raw', value=msg)

9. 异常捕获
   └─> 记录发送日志，单条失败不影响主循环

10. 循环控制
    └─> 休眠 30 秒

11. 异步线程工作
    └─> 守护线程从队列取数据，批量写入 MySQL 维度表

12. 结束一轮
    └─> 记录日志，进入下一轮
```

---

# 架构红线 (Architecture Red Lines)

## 1. 职责分离
- Python 仅负责：爬取、清洗、NLP分析、写入维度表（`weibo_base`, `weibo_analysis`）、发送Kafka
- **禁止**：Python 向 `weibo_trend` 写入任何数据
- **禁止**：Python 向已废除的 `weibo_current` 写入任何数据
- **禁止**：Python 主循环中同步等待数据库写入完成
- **禁止**：**严禁基于排名/热度变化过滤 Kafka 消息**。所有爬取到的热搜必须全量发送 Kafka，否则 Flink 水位线会停滞。缓存仅用于避免重复 NLP 计算。

## 2. 异步写入架构（必须实现）
```python
# 目标架构
主爬虫线程 ──> Queue ──> 后台守护线程 ──> 批量写入 MySQL (weibo_base, weibo_analysis)
                ↓
         NLP线程池（情感+话题分析）
                ↓
         Kafka发送（异步）
```

**具体要求**：
- 使用 `queue.Queue` + `threading.Thread(daemon=True)`
- 批量阈值：满100条或每5秒强制刷盘
- 主线程只负责 `queue.put()`，严禁直接操作数据库

## 3. NLP模块（新增）

### 3.1 单条分析
```python
class NLPPipeline:
    def analyze(self, title: str) -> dict:
        """
        返回: {
            "sentiment_score": float,  # -1到1（负向到正向）
            "type_name": str,          # 娱乐/社会/科技/体育/财经
            "topic_name": str          # 如"刘畊宏健身热潮"
        }
        
        实现要求：模拟即可
        - sentiment_score: 基于关键词规则（如"恭喜"->1.0，"悲剧"->-1.0）
          ⚠️ **重要**：若使用SnowNLP等0-1范围库，必须转换：`(score * 2) - 1`
        - type_name: 基于关键词匹配分类
        - topic_name: 提取中心关键词+后缀（如"刘畊宏"->"刘畊宏健身热潮"）
        """
```

### 3.2 话题聚类
```python
class TopicClusterer:
    def cluster_batch(self, items: list[HotSearchItem]) -> dict:
        """
        输入: 批量热搜列表
        输出: {item_id: {"topic_name": str, "keyword": str}}
        
        实现思路（模拟即可）：
        1. 提取中心关键词（如"刘畊宏"、"疫情"）
        2. 相同关键词归为同一话题
        3. 生成话题名称：keyword + "热潮"/"事件"/"话题"
        """
```

### 3.3 Redis缓存策略
- **Key**: `nlp_cache:{item_id}` (item_id为title的MD5)
- **Value**: `{"sentiment_score": 0.5, "type_name": "娱乐", "topic_name": "xxx"}`
- **TTL**: 86400秒（24小时，因为热搜生命周期短）
- **逻辑**：
  1. 先查缓存，命中则直接用
  2. 未命中则调用NLP分析
  3. 分析结果双写：Redis缓存 + 异步DB队列
- **⚠️ 重要说明**：缓存仅用于避免重复 NLP 计算，**不影响 Kafka 消息发送**。所有物品无论缓存是否命中，都必须发送 Kafka。

## 4. Kafka消息契约

```json
{
  "item_id": "md5_hash_string",
  "title": "原始标题",
  "rank_pos": 1,
  "heat": 100,
  "crawl_time": 1715623400000,
  "sentiment_score": 0.85,
  "topic_name": "刘畊宏健身热潮",
  "type_name": "娱乐",
  "source": "weibo"
}
```

**严禁**：任何字段为null，失败时给默认值：
- sentiment_score: 0（中性）
- topic_name: "其他话题"
- type_name: "未知"

## 5. 配置解耦
- 所有类必须通过构造函数接收配置，禁止直接导入 `settings.py`
- `main.py` 负责组装依赖并注入

## 6. 健壮性
- 所有外部调用（HTTP、DB、Redis、Kafka）必须包裹 `try-except`
- 异常只记录日志，**禁止抛出导致程序退出**
- 单条数据处理失败不影响其他数据

---

# 重构任务清单

## Phase 1: 删除违规代码
- [ ] **删除** `mysql_client.py` 中 `save_incremental_data()` 方法对 `weibo_trend` 的写入（第64-69行、第79-83行、第89行）
- [ ] **删除** `mysql_client.py` 中 `save_to_current()` 方法（整个方法删除，`weibo_current`表已废除）
- [ ] **删除** `getRealtimeWithCrawler.py` 第94行的非法调用

## Phase 2: 异步架构改造
- [ ] 在 `storage/` 下新建 `async_writer.py`，实现队列+守护线程模式
  - 队列类型：`queue.Queue`
  - 守护线程：批量写入（100条或5秒阈值）
  - 写入目标：
    - `weibo_base`：**`INSERT IGNORE`**（保护 first_time，首次写入后不再更新）
    - `weibo_analysis`：**`INSERT ... ON DUPLICATE KEY UPDATE`**（允许缓存过期后更新情感分）
  - **退出机制**：程序退出时，尝试清空队列后再结束守护线程（可选，若实现复杂可接受数据丢失）
- [ ] 改造 `mysql_client.py`：
  - 提供批量写入接口 `batch_write_base(items)` -> 使用 `INSERT IGNORE`
  - 提供批量写入接口 `batch_write_analysis(items)` -> 使用 `INSERT ... ON DUPLICATE KEY UPDATE`
  - **⚠️ 严禁**：使用 `INSERT IGNORE` 写入 analysis 表，必须允许更新情感分
  - 删除同步写入方法
- [ ] 改造 `main.py`：
  - 主线程只负责 `queue.put()`
  - 启动时初始化异步写入守护线程

## Phase 3: 新增NLP模块
- [ ] 新建 `process/nlp_pipeline.py`：
  - 实现情感分析（-1到1）
    - ⚠️ **若使用0-1范围库（如SnowNLP），必须转换：`(score * 2) - 1`**
  - 实现分类（娱乐/社会/科技等）
  - **调用 topic_clusterer.py 完成话题生成**（明确调用链，避免逻辑重复）
  - **合并原 deduplicationer.py 逻辑**：基于Redis缓存判断是否需要NLP分析
- [ ] 新建 `process/topic_clusterer.py`：
  - 实现批量话题聚类
  - 基于关键词相似度算法（模拟即可）
  - 被 nlp_pipeline.py 调用，不独立对外暴露
- [ ] 集成Redis缓存：
  - 查询 Key: `nlp_cache:{item_id}`
  - 写入 Key: `nlp_cache:{item_id}` (TTL 86400s)
  - ⚠️ **注意**：缓存仅用于避免重复NLP计算，不影响Kafka消息发送。所有物品必须发送Kafka。

## Phase 4: 配置解耦
- [ ] 所有类必须通过构造函数接收配置
- [ ] `main.py` 统一组装依赖并注入

**期望的配置结构示例**：
```python
config = {
    "DB": {
        "HOST": "localhost",
        "PORT": 3306,
        "USER": "root",
        "PASSWORD": "your_password",
        "DB_NAME": "social_platforms_analysis"
    },
    "REDIS": {
        "HOST": "localhost",
        "PORT": 6379,
        "DB": 0
    },
    "KAFKA": {
        "BOOTSTRAP_SERVERS": "localhost:9092",
        "TOPIC": "weibo_raw"
    },
    "CRAWLER": {
        "SLEEP_SECONDS": 30
    }
}
```

## Phase 5: 改造主流程
- [ ] 重写 `main.py` 主循环，严格遵循业务流程
- [ ] 删除 `weibo_current` 写入逻辑
- [ ] 集成NLP缓存筛查
- [ ] 集成异步队列写入

---

# 开发规范与要求

## 1. 模块化设计（Mandatory）
**核心原则**：每个模块必须独立、可替换、无强耦合

```
✅ 正确示范：
  main.py ──> NLPModule.analyze()  # 只需调用接口，不关心内部实现
  main.py ──> AsyncWriter.enqueue() # 只需放入队列，不关心写入细节

❌ 错误示范：
  main.py 直接操作 NLPModule 内部的分词器、模型等细节
```

**模块边界**：
- `CrawlerModule`：只负责爬取，返回原始数据
- `CleanerModule`：只负责清洗，返回标准对象
- `NLPModule`：只负责分析，输入标题输出分析结果
- `CacheModule`：只负责Redis读写
- `AsyncWriterModule`：只负责队列管理和批量写入
- `KafkaModule`：只负责消息发送

**任意模块可替换**：
- 如需更换NLP算法，只需实现相同的 `analyze(title) -> dict` 接口
- 如需更换存储，只需实现相同的 `enqueue(item) -> bool` 接口

## 2. 工具使用（Recommended）
**允许并鼓励使用子任务分解**：
- 每个Phase可作为独立子任务
- 复杂模块（如NLP、AsyncWriter）可单独子任务实现
- 使用工具辅助：代码检查、依赖分析、性能测试

## 3. 注释规范（Mandatory）
**目标读者**：NLP新手也能看懂

**模块级注释**（每个文件顶部）：
```python
"""
模块名称: nlp_pipeline.py
模块职责: 自然语言处理流水线，负责情感分析、分类、话题生成
输入接口: analyze(title: str) -> dict
输出格式: {"sentiment_score": float, "type_name": str, "topic_name": str}
依赖模块: 无（纯算法模块）
作者备注: 当前使用基于关键词的规则实现，可替换为深度学习模型
"""
```

**函数级注释**：
```python
def analyze(self, title: str) -> dict:
    """
    对热搜标题进行NLP分析
    
    Args:
        title: 热搜标题文本，如"刘畊宏直播健身火爆全网"
    
    Returns:
        dict: 包含三个字段的分析结果
            - sentiment_score: 情感分数，范围-1(负面)到1(正面)
            - type_name: 内容分类，如"娱乐"、"社会"、"科技"
            - topic_name: 话题名称，如"刘畊宏健身热潮"
    
    实现逻辑:
        1. 提取关键词（如"刘畊宏"）
        2. 基于关键词词典判断情感倾向
        3. 基于规则生成分类和话题名
    """
```

**关键逻辑注释**（行内）：
```python
# Step 1: 提取核心关键词（如"刘畊宏"、"疫情"等）
keyword = self._extract_keyword(title)

# Step 2: 查询情感词典判断正负面
# 原理：统计标题中正面词("恭喜"/"成功")和负面词("悲剧"/"灾难")的数量
sentiment = self._calc_sentiment(title)
```

---

# 输出要求

## 输出策略（Important）
- **分 Phase 输出**：请先输出 **Phase 1 & 2** 的代码。待我确认无误后，再输出 **Phase 3 & 4**。
- **完整性**：每个文件必须完整，不要省略 import 或结尾。
- **优先保证架构合规**：若代码长度受限，优先保证 `main.py`, `async_writer.py`, `nlp_pipeline.py` 的完整性。

## 具体要求

1. **先指出所有违规点**：列出违反上述红线的具体代码位置和原因
2. **给出重构后的完整代码**：按文件组织，不要省略任何代码
3. **每个文件顶部添加模块注释**：包含职责、接口、依赖、备注
4. **关键逻辑添加行内注释**：解释"为什么这样做"而非"做了什么"
5. **保持原有功能**：确保重构后仍能正确爬取、去重、发送Kafka
6. **生成总结文档**：在 `docs/` 下创建 `summary.md`，包含：
   - 重构流程概览（Step by Step）
   - 重要改动点（Architecture Changes）
   - 重要知识点（Key Learnings）
   - 模块依赖图（可选）

**特别注意**：
- `kafka_producer.py` 的异步发送设计良好，保留但需确保配置注入
- `item.py` 的 `to_dict()` 方法可能需要扩展
- `deduplicationer.py` **已删除**，其逻辑并入 `nlp_pipeline.py`
- **严禁**出现任何对 `weibo_trend` 或 `weibo_current` 的写入操作
