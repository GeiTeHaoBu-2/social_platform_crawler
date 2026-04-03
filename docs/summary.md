# 微博热搜爬虫重构总结文档

## 重构流程概览（Step by Step）

### Phase 1: 删除违规代码

| 文件 | 修改内容 | 原因 |
|------|----------|------|
| `mysql_client.py` | 删除`save_incremental_data()`中对`weibo_trend`的写入 | **红线**: Python禁止写入趋势表 |
| `mysql_client.py` | 删除`save_to_current()`整个方法 | **红线**: `weibo_current`表已废除 |
| `getRealtimeWithCrawler.py` | 删除第94行非法调用`get_realtime_data()` | 模块导入时不应执行爬虫 |

### Phase 2: 异步架构改造

| 文件 | 新增/修改 | 说明 |
|------|-----------|------|
| `async_writer.py` (新建) | 异步写入器 | 实现queue.Queue + threading.Thread(daemon=True)模式 |
| `mysql_client.py` | 新增批量接口 | `batch_write_base()`(INSERT IGNORE) + `batch_write_analysis()`(ON DUPLICATE KEY UPDATE) |
| `mysql_client.py` | 配置解耦 | 通过构造函数接收配置，禁止直接import settings |

**异步架构设计**:
```
主爬虫线程 ──> Queue ──> 后台守护线程 ──> 批量写入MySQL
                ↓
         NLP线程池（情感+话题分析）
                ↓
         Kafka发送（异步）
```

### Phase 3: 新增NLP模块

| 文件 | 职责 | 关键功能 |
|------|------|----------|
| `nlp_pipeline.py` (新建) | NLP流水线 | 情感分析(-1~1)、分类、话题生成、缓存筛查 |
| `topic_clusterer.py` (新建) | 话题聚类 | 基于关键词生成话题名称 |

**NLP缓存策略**:
- Key: `nlp_cache:{item_id}` (item_id为title的MD5)
- Value: `{"sentiment_score": 0.5, "type_name": "娱乐", "topic_name": "xxx"}`
- TTL: 86400秒（24小时）
- **重要**: 缓存仅用于避免重复NLP计算，**不影响Kafka消息发送**

### Phase 4: 配置解耦

| 文件 | 修改 | 说明 |
|------|------|------|
| `mysql_client.py` | `__init__(self, config, platform)` | 通过参数接收配置 |
| `AsyncWriter` | `__init__(self, db_config, platform)` | 通过参数接收配置 |
| `NLPPipeline` | `__init__(self, redis_config=None)` | 通过参数接收配置，可为None使用默认 |
| `main.py` | 组装配置并注入 | 统一配置组装和依赖注入 |

### Phase 5: 改造主流程

**新业务流程**:
```
1. 加载配置
   └─> main.py组装配置并注入到各组件

2. 初始化组件
   └─> 初始化Cleaner、NLPPipeline、AsyncWriter、KafkaProducer
   └─> 启动AsyncWriter守护线程

3. 调度爬虫
   └─> 主控制程序触发爬取任务

4. 爬取与清洗
   └─> get_realtime_data()获取原始数据
   └─> Cleaner.clean()清洗标题，生成item_id = MD5(title)

5. 更新实时缓存 (Redis ZSet)
   └─> Key: weibo:realtime_rank
   └─> Score: 热度值(heat)
   └─> Member: item_id
   └─> 目的：支持前端按热度排序查询

6. NLP 缓存筛查
   └─> 查询 Redis `nlp_cache:{item_id}`
       ├─> 命中：直接读取 sentiment, topic_name, type_name
       └─> 未命中：
           ├─> 调用NLP分析
           ├─> 结果放入异步DB队列 (写 weibo_base + weibo_analysis)
           └─> 写入 Redis 缓存

7. 异步队列写入MySQL
   └─> 主线程enqueue_base() / enqueue_analysis()
   └─> 守护线程批量写入（100条或5秒）

8. 全量发送Kafka
   └─> 所有热搜必须发送，严禁过滤
   └─> producer.send(topic='weibo_raw', value=msg)

9. 循环控制
   └─> 休眠30秒

10. 结束处理
    └─> 尝试清空队列后结束守护线程
```

---

## 重要改动点（Architecture Changes）

### 1. 职责分离

**Python负责**:
- ✅ 爬取原始数据
- ✅ 数据清洗
- ✅ NLP分析（带缓存）
- ✅ 写入维度表（`weibo_base`, `weibo_analysis`）
- ✅ 全量发送Kafka

**Python禁止**:
- ❌ 写入`weibo_trend`表（Flink负责）
- ❌ 写入`weibo_current`表（已废除）
- ❌ 主循环中同步等待数据库写入
- ❌ 基于排名/热度变化过滤Kafka消息

### 2. 异步写入架构

**旧架构（同步阻塞）**:
```python
# 主线程直接写入，阻塞爬虫
mysql_client.save_incremental_data(items)  # 同步阻塞
```

**新架构（异步非阻塞）**:
```python
# 主线程只入队，不等待
async_writer.enqueue_base(item)  # 非阻塞
async_writer.enqueue_analysis(item)  # 非阻塞
# 守护线程批量写入
```

### 3. 缓存策略澄清

**重要区分**:

| 缓存类型 | 用途 | 影响Kafka? |
|----------|------|------------|
| NLP缓存 | 避免重复NLP计算 | **否，所有item都发Kafka** |
| 老dedup缓存 | 过滤已发送的item | **是，违规！已删除** |

**红线重申**: 缓存仅用于优化NLP计算，**严禁**用于过滤Kafka消息。

### 4. 数据库写入策略

| 表名 | SQL策略 | 说明 |
|------|---------|------|
| `weibo_base` | `INSERT IGNORE` | 保护first_time，首次写入后不再更新 |
| `weibo_analysis` | `INSERT ... ON DUPLICATE KEY UPDATE` | 允许更新情感分（缓存过期后重新分析） |
| `weibo_trend` | **Python禁止写入** | Flink负责写入 |

---

## 重要知识点（Key Learnings）

### 1. Kafka全量发送原则

**为什么必须全量发送？**
- Flink依赖Kafka消息驱动水位线（Watermark）
- 如果Python过滤消息，Flink接收不到某些rank/heat的变化
- 导致Flink窗口计算停滞或结果不准确

**正确做法**:
- Python发送全量数据到Kafka
- Flink消费后自行判断是否需要更新
- 冗余数据在Flink端处理，不在Python端过滤

### 2. INSERT IGNORE vs ON DUPLICATE KEY UPDATE

| 场景 | 推荐SQL | 原因 |
|------|---------|------|
| 首次记录时间 | INSERT IGNORE | 保护first_time不被覆盖 |
| 可更新的分析结果 | ON DUPLICATE KEY UPDATE | 允许情感分过期更新 |

### 3. 异步写入的批量阈值设计

| 阈值 | 值 | 设计考虑 |
|------|-----|----------|
| 数量阈值 | 100条 | 平衡内存占用和写入效率 |
| 时间阈值 | 5秒 | 避免数据在队列中停留过久 |

### 4. 配置解耦的好处

**旧方式（紧耦合）**:
```python
from common.config.settings import MYSQL_CONFIG
# 无法单元测试，无法多环境部署
```

**新方式（解耦注入）**:
```python
def __init__(self, config: Dict[str, Any]):
    self.config = config
# 便于单元测试、多环境配置、模块替换
```

### 5. 守护线程的生命周期管理

```python
# 启动
async_writer.start()  # 启动守护线程

# 停止
async_writer.stop()   # 设置停止标志 -> 刷空队列 -> 关闭连接
```

**注意**: 守护线程在程序退出时会自动结束，但可能丢失队列中未写入的数据。建议主动调用`stop()`。

---

## 模块依赖图

```
main.py (主入口)
├── platforms/sina/getRealtimeWithCrawler.py (爬虫)
├── process/cleaner.py (清洗)
├── process/nlp_pipeline.py (NLP分析)
│   └── process/topic_clusterer.py (话题聚类)
├── storage/async_writer.py (异步写入)
│   └── storage/mysql_client.py (MySQL客户端)
├── storage/redis_client.py (Redis缓存)
└── transmit/kafka_producer.py (Kafka发送)
```

---

## 待办事项（后续优化）

1. **NLP算法升级**: 当前使用关键词规则，可替换为深度学习模型（如BERT）
2. **监控告警**: 增加写入失败告警、队列积压告警
3. **配置中心**: 引入etcd/consul实现配置动态刷新
4. **容器化**: 添加Dockerfile和docker-compose.yml
