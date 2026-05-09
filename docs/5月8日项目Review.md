# 社会舆情实时分析系统 - Python端 Code Review

**项目名称**: 基于Python+Java+MySQL的社会舆情实时分析系统  
**Review日期**: 2026年5月8日  
**代码规模**: 约1980行Python代码  
**技术栈**: Python 3.10+ / MySQL / Redis / Kafka / LLM API

---

## 一、项目架构总览

### 1.1 整体架构设计 ⭐⭐⭐⭐⭐

**优点**:
- ✅ **职责分离清晰**: 严格遵循分层架构（platforms → process → storage → transmit）
- ✅ **模块化设计**: 每个模块职责单一，符合单一职责原则（SRP）
- ✅ **依赖方向正确**: main.py → process → storage → models，无循环依赖
- ✅ **配置集中管理**: 通过 `settings.py` + `.env` 统一管理配置

**架构亮点**:
```
├── platforms/    # 数据采集层 - 只负责爬取，不涉及存储
├── process/      # 数据处理层 - 清洗、分析、计算
├── storage/      # 数据存储层 - MySQL/Redis操作
├── transmit/     # 消息传输层 - Kafka消息发送
├── models/       # 数据模型层 - 纯数据结构，无业务逻辑
└── config/       # 配置层 - 环境变量加载
```

**改进建议**:
- 📌 建议增加 `common/exceptions/` 目录，统一管理自定义异常
- 📌 建议增加 `common/constants/` 目录，统一管理常量定义

---

## 二、核心模块深度Review

### 2.1 主流程调度 (main.py) ⭐⭐⭐⭐

**代码质量**: 良好

**优点**:
- ✅ 流程编排清晰，7步流水线一目了然
- ✅ 异常处理完善，使用 try-except 包裹整个流程
- ✅ 日志记录充分，每步都有明确的日志输出
- ✅ 资源管理规范，在 `stop()` 中正确关闭连接

**问题诊断**:

#### 🔴 严重问题1: 缺少类型注解
```python
# 当前代码 (main.py:23)
class HotSearchPipeline:
    def __init__(self):
        self.cleaner = Cleaner()
        
# 建议改进
class HotSearchPipeline:
    def __init__(self) -> None:
        self.cleaner: Cleaner = Cleaner()
```

#### 🟡 中等问题2: 硬编码平台名称
```python
# 当前代码 (main.py:32)
self.writer = AsyncWriter(CONFIG['DB'], platform='weibo')

# 问题: 如果需要支持多平台，需要重构
# 建议: 通过配置或参数传入平台名称
```

#### 🟡 中等问题3: 缺少优雅退出机制
```python
# 当前代码 (main.py:140-150)
def run_forever(self):
    self.start()
    try:
        while self._running:
            self.run_once()
            logger.info(f"本轮完成，休眠 {self.sleep_seconds} 秒...\n")
            time.sleep(self.sleep_seconds)
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")
    finally:
        self.stop()

# 问题: 
# 1. 只捕获 KeyboardInterrupt，未处理其他信号（如 SIGTERM）
# 2. 休眠期间无法响应中断信号
# 3. 缺少健康检查机制

# 建议改进
import signal

def run_forever(self):
    self.start()
    
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备优雅退出...")
        self._running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        while self._running:
            self.run_once()
            # 分段休眠，提高响应速度
            for _ in range(self.sleep_seconds):
                if not self._running:
                    break
                time.sleep(1)
    except Exception as e:
        logger.error(f"主循环异常: {e}")
    finally:
        self.stop()
```

#### 🟢 优化建议4: 增加监控指标
```python
# 建议增加统计信息
class HotSearchPipeline:
    def __init__(self):
        self._total_runs = 0
        self._success_runs = 0
        self._failed_runs = 0
        self._start_time = time.time()
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_runs': self._total_runs,
            'success_runs': self._success_runs,
            'failed_runs': self._failed_runs,
            'uptime': time.time() - self._start_time,
            'success_rate': self._success_runs / max(self._total_runs, 1) * 100
        }
```

---

### 2.2 数据模型 (models/item.py) ⭐⭐⭐⭐⭐

**代码质量**: 优秀

**优点**:
- ✅ 使用 `@property` 实现延迟计算 `item_id`
- ✅ 提供多种序列化方法 (`to_dict`, `to_kafka_dict`)
- ✅ 使用 MD5 生成唯一标识，避免重复
- ✅ 类型注解完整

**改进建议**:

#### 🟢 优化建议1: 使用 dataclass 简化代码
```python
# 当前代码使用普通类，需要手动编写 __init__
# 建议使用 Python 3.7+ 的 dataclass

from dataclasses import dataclass, field
from typing import Optional
import hashlib

@dataclass
class HotSearchItem:
    rank: int
    title: str
    url: str
    heat: int
    latest_crawl_time: int
    first_on_board_time: Optional[int] = None
    _item_id: Optional[str] = field(default=None, repr=False)
    heat_diff: int = 0
    rank_diff: int = 0
    sentiment_score: Optional[float] = None
    type_name: Optional[str] = None
    topic_name: Optional[str] = None
    
    def __post_init__(self):
        if self.first_on_board_time is None:
            self.first_on_board_time = self.latest_crawl_time
    
    @property
    def item_id(self) -> str:
        if self._item_id is None:
            self._item_id = hashlib.md5(self.title.encode('utf-8')).hexdigest()
        return self._item_id
```

**优势**:
- 自动生成 `__init__`, `__repr__`, `__eq__` 等方法
- 代码更简洁，可读性更强
- 支持不可变对象（`frozen=True`）

---

### 2.3 爬虫模块 (platforms/sina/getRealtimeWithCrawler.py) ⭐⭐⭐⭐

**代码质量**: 良好

**优点**:
- ✅ 职责单一，只负责数据采集
- ✅ 异常处理完善，捕获 `RequestException`
- ✅ 使用正则表达式提取数字，处理能力强
- ✅ 时间戳统一管理

**问题诊断**:

#### 🔴 严重问题1: 缺少重试机制
```python
# 当前代码 (getRealtimeWithCrawler.py:24-32)
try:
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    logger.error(f"请求失败：{e}")
    return []

# 问题: 网络波动或临时故障会导致数据丢失
# 建议: 增加重试机制

import time
from typing import List

def get_realtime_data(max_retries: int = 3, retry_delay: int = 2) -> List[HotSearchItem]:
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            response.encoding = 'utf-8'
            logger.info(f"请求成功！尝试次数: {attempt + 1}")
            break
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
            else:
                logger.error(f"达到最大重试次数，放弃请求")
                return []
    
    # 后续解析逻辑...
```

#### 🟡 中等问题2: Cookie 失效检测不足
```python
# 当前代码只检查 tbody 是否存在
if hot_search_table is None:
    logger.error("未找到热搜列表表格，请检查页面结构或Cookie是否有效")
    return []

# 建议: 增加更详细的检测
if hot_search_table is None:
    # 检查是否被重定向到登录页
    if 'login' in response.url or 'passport' in response.url:
        logger.error("Cookie已失效，请更新WEIBO_COOKIE配置")
    else:
        logger.error("页面结构可能已变化，请检查HTML解析逻辑")
    return []
```

#### 🟡 中等问题3: 缺少请求限流保护
```python
# 建议: 增加请求间隔控制
import time

LAST_REQUEST_TIME = 0
MIN_REQUEST_INTERVAL = 5  # 最小请求间隔（秒）

def get_realtime_data() -> List[HotSearchItem]:
    global LAST_REQUEST_TIME
    
    # 限流保护
    elapsed = time.time() - LAST_REQUEST_TIME
    if elapsed < MIN_REQUEST_INTERVAL:
        wait_time = MIN_REQUEST_INTERVAL - elapsed
        logger.info(f"请求过快，等待 {wait_time:.1f} 秒...")
        time.sleep(wait_time)
    
    LAST_REQUEST_TIME = time.time()
    # 后续请求逻辑...
```

#### 🟢 优化建议4: 使用 Session 复用连接
```python
# 当前代码每次请求都创建新连接
# 建议: 使用 requests.Session 复用 TCP 连接

import requests

# 模块级别 Session
_session = None

def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(headers)
    return _session

def get_realtime_data() -> List[HotSearchItem]:
    session = _get_session()
    response = session.get(url, timeout=10)
    # 后续逻辑...
```

---

### 2.4 数据清洗模块 (process/cleaner.py) ⭐⭐⭐

**代码质量**: 基础

**优点**:
- ✅ 代码简洁
- ✅ 职责单一

**问题诊断**:

#### 🔴 严重问题1: 清洗逻辑过于简单
```python
# 当前代码 (cleaner.py:6-11)
def clean(self, raw_data: List[HotSearchItem]) -> List[HotSearchItem]:
    for item in raw_data:
        if item.title:
            item.title = item.title.strip()
        if item.url:
            item.url = item.url.strip()
    return raw_data

# 问题:
# 1. 只做了简单的 strip()，缺少深度清洗
# 2. 未处理异常数据（如空标题、无效URL）
# 3. 未去重
# 4. 直接修改原对象，不符合函数式编程原则

# 建议改进
from typing import List
import re

class Cleaner:
    def clean(self, raw_data: List[HotSearchItem]) -> List[HotSearchItem]:
        """
        数据清洗主入口
        
        清洗规则:
        1. 去除首尾空格
        2. 过滤空标题
        3. 验证URL格式
        4. 去重（基于item_id）
        5. 标题规范化（去除多余空格、特殊字符）
        """
        if not raw_data:
            return []
        
        cleaned_items = []
        seen_ids = set()
        
        for item in raw_data:
            # 1. 空值检查
            if not item.title or not item.title.strip():
                logger.warning(f"跳过空标题条目: rank={item.rank}")
                continue
            
            # 2. 标题清洗
            item.title = self._clean_title(item.title)
            
            # 3. URL验证
            if item.url:
                item.url = self._clean_url(item.url)
            
            # 4. 去重
            if item.item_id in seen_ids:
                logger.debug(f"跳过重复条目: {item.title[:20]}")
                continue
            seen_ids.add(item.item_id)
            
            cleaned_items.append(item)
        
        logger.info(f"清洗完成: 输入{len(raw_data)}条 -> 输出{len(cleaned_items)}条")
        return cleaned_items
    
    def _clean_title(self, title: str) -> str:
        """标题清洗"""
        # 去除首尾空格
        title = title.strip()
        # 去除多余空格
        title = ' '.join(title.split())
        # 去除特殊控制字符
        title = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', title)
        return title
    
    def _clean_url(self, url: str) -> str:
        """URL清洗"""
        url = url.strip()
        # 简单验证URL格式
        if not url.startswith(('http://', 'https://')):
            logger.warning(f"无效URL格式: {url}")
            return ''
        return url
```

---

### 2.5 LLM分析模块 (process/llm_analyzer.py) ⭐⭐⭐⭐⭐

**代码质量**: 优秀

**优点**:
- ✅ **架构设计优秀**: 主类 + 子模块（cache/client/prompts）分离
- ✅ **缓存机制完善**: Redis缓存 + 命中率统计
- ✅ **批量处理优化**: 支持批量API调用，减少网络开销
- ✅ **降级策略**: API失败时使用默认值
- ✅ **日志详细**: 每条处理结果都有日志输出

**问题诊断**:

#### 🟡 中等问题1: 缺少并发控制
```python
# 当前代码 (llm_analyzer.py:257-278)
def _analyze_in_batches(self, titles: List[str]) -> List[Dict[str, Any]]:
    all_results = []
    for i in range(0, len(titles), self.BATCH_SIZE):
        batch_results = self._call_batch_api(batch)
        all_results.extend(batch_results)

# 问题: 串行处理，如果批次较多会耗时较长
# 建议: 使用异步或线程池并发处理

import asyncio
from concurrent.futures import ThreadPoolExecutor

async def _analyze_in_batches_async(self, titles: List[str]) -> List[Dict[str, Any]]:
    """异步批量分析"""
    batches = [titles[i:i + self.BATCH_SIZE] 
               for i in range(0, len(titles), self.BATCH_SIZE)]
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(executor, self._call_batch_api, batch)
            for batch in batches
        ]
        results = await asyncio.gather(*tasks)
    
    all_results = []
    for batch_results in results:
        all_results.extend(batch_results)
    
    return all_results
```

#### 🟢 优化建议2: 增加熔断机制
```python
# 当LLM服务持续不可用时，应该快速失败而不是持续重试
# 建议增加熔断器模式

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.last_failure_time = 0
        self.state = 'CLOSED'  # CLOSED, OPEN, HALF_OPEN
    
    def call(self, func, *args, **kwargs):
        if self.state == 'OPEN':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'HALF_OPEN'
            else:
                raise Exception("Circuit breaker is OPEN")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        self.failure_count = 0
        self.state = 'CLOSED'
    
    def _on_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = 'OPEN'
```

---

### 2.6 LLM客户端 (process/llm_client.py) ⭐⭐⭐⭐⭐

**代码质量**: 优秀

**优点**:
- ✅ **故障转移机制完善**: 支持主备模型自动切换
- ✅ **重试策略合理**: 指数退避 + 最大重试次数
- ✅ **错误分类处理**: 区分 429/401/500 等不同错误
- ✅ **JSON解析健壮**: 支持多种格式提取

**亮点设计**:
```python
# 故障转移策略 (llm_client.py:94-130)
def _switch_model(self, reason: str):
    """切换到下一个可用模型"""
    next_model = self._get_next_model()
    if next_model:
        old_model = self.current_model
        self.current_model = next_model
        self.consecutive_failures = 0
        logger.warning(f"🔄 [LLM模型切换] {old_model} -> {next_model}")
```

**改进建议**:

#### 🟢 优化建议1: 增加请求/响应日志
```python
# 建议记录完整的请求和响应，便于调试
def _do_chat_request(self, model_config, messages, temperature, max_tokens):
    request_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    logger.debug(f"[{request_id}] 请求URL: {model_config['api_url']}")
    logger.debug(f"[{request_id}] 请求Payload: {json.dumps(payload, ensure_ascii=False)[:500]}")
    
    # ... 发送请求 ...
    
    logger.debug(f"[{request_id}] 响应状态: {response.status_code}")
    logger.debug(f"[{request_id}] 响应内容: {content[:500]}")
```

---

### 2.7 Redis管理器 (storage/redis_manager.py) ⭐⭐⭐⭐

**代码质量**: 良好

**优点**:
- ✅ 连接管理规范，支持自动重连
- ✅ 使用 Pipeline 批量操作，提高性能
- ✅ 异常处理完善

**问题诊断**:

#### 🟡 中等问题1: 缺少连接池配置
```python
# 当前代码 (redis_manager.py:20-26)
self.client = redis.Redis(
    host=self.config.get('host', '127.0.0.1'),
    port=self.config.get('port', 6379),
    db=self.config.get('db', 0),
    password=self.config.get('password') or None,
    decode_responses=True
)

# 问题: 使用默认连接池配置，高并发时可能性能不佳
# 建议: 显式配置连接池

import redis

self.client = redis.Redis(
    host=self.config.get('host', '127.0.0.1'),
    port=self.config.get('port', 6379),
    db=self.config.get('db', 0),
    password=self.config.get('password') or None,
    decode_responses=True,
    max_connections=50,  # 最大连接数
    socket_connect_timeout=5,  # 连接超时
    socket_timeout=5,  # 读写超时
    retry_on_timeout=True  # 超时重试
)
```

#### 🟢 优化建议2: 增加批量操作方法
```python
# 建议: 增加批量获取方法
def batch_get(self, keys: List[str]) -> Dict[str, Any]:
    """批量获取缓存"""
    if not self._ensure_connection():
        return {}
    
    try:
        pipeline = self.client.pipeline()
        for key in keys:
            pipeline.get(key)
        results = pipeline.execute()
        
        return {
            key: json.loads(value) if value else None
            for key, value in zip(keys, results)
        }
    except Exception as e:
        logger.error(f"批量获取缓存失败: {e}")
        return {}
```

---

### 2.8 MySQL客户端 (storage/mysql_client.py) ⭐⭐⭐⭐

**代码质量**: 良好

**优点**:
- ✅ 批量写入使用 `executemany`，性能优秀
- ✅ 事务管理规范，失败时正确回滚
- ✅ SQL注入防护，使用参数化查询

**问题诊断**:

#### 🔴 严重问题1: 缺少连接池
```python
# 当前代码 (mysql_client.py:15-23)
self.connection = pymysql.connect(
    host=config.get('host', '127.0.0.1'),
    port=config.get('port', 3306),
    # ...
    autocommit=False
)

# 问题: 
# 1. 每个线程创建独立连接，资源消耗大
# 2. 连接断开后无法自动重连
# 3. 缺少连接健康检查

# 建议: 使用 DBUtils 连接池
from dbutils.pooled_db import PooledDB
import pymysql

class MySQLClient:
    __pool = None
    
    @classmethod
    def _get_pool(cls, config):
        if cls.__pool is None:
            cls.__pool = PooledDB(
                creator=pymysql,
                maxconnections=20,  # 最大连接数
                mincached=2,  # 初始空闲连接数
                maxcached=10,  # 最大空闲连接数
                host=config.get('host', '127.0.0.1'),
                port=config.get('port', 3306),
                user=config.get('user', 'root'),
                password=config.get('password', ''),
                database=config.get('database', ''),
                charset=config.get('charset', 'utf8mb4'),
                autocommit=False
            )
        return cls.__pool
    
    def __init__(self, config, platform='weibo'):
        self.pool = self._get_pool(config)
        self.connection = self.pool.connection()
        # ...
```

#### 🟡 中等问题2: 缺少连接健康检查
```python
# 建议: 增加连接检查方法
def _ensure_connection(self) -> bool:
    """确保连接可用"""
    try:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return True
    except Exception:
        logger.warning("MySQL连接已断开，尝试重连...")
        try:
            self.connection = self.pool.connection()
            return True
        except Exception as e:
            logger.error(f"MySQL重连失败: {e}")
            return False
```

#### 🟢 优化建议3: 增加查询方法
```python
# 当前只有写入方法，建议增加查询方法
def query(self, sql: str, params: tuple = None) -> List[Dict]:
    """执行查询并返回字典列表"""
    if not self._ensure_connection():
        return []
    
    try:
        with self.connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"查询失败: {e}")
        return []
```

---

### 2.9 异步写入器 (storage/async_writer.py) ⭐⭐⭐⭐⭐

**代码质量**: 优秀

**优点**:
- ✅ **架构设计优秀**: 队列 + 守护线程模式
- ✅ **批量写入优化**: 自动攒批，减少数据库压力
- ✅ **异常处理完善**: 重试机制 + 优雅退出
- ✅ **资源管理规范**: 正确关闭数据库连接

**亮点设计**:
```python
# 批量写入策略 (async_writer.py:133-142)
should_flush = (
    len(buffer) >= self.BATCH_SIZE or  # 达到批次大小
    (buffer and current_time - last_flush_time >= self.FLUSH_INTERVAL)  # 或超时
)
```

**改进建议**:

#### 🟢 优化建议1: 增加队列监控
```python
# 建议: 增加队列状态监控
def get_queue_status(self) -> Dict[str, int]:
    """获取队列状态"""
    return {
        'base_queue_size': self.base_queue.qsize(),
        'analysis_queue_size': self.analysis_queue.qsize(),
        'trend_queue_size': self.trend_queue.qsize(),
        'base_queue_max': self.base_queue.maxsize if hasattr(self.base_queue, 'maxsize') else 'unlimited',
    }
```

#### 🟢 优化建议2: 增加背压控制
```python
# 当前队列无限大，可能导致内存溢出
# 建议: 设置队列最大长度

def __init__(self, db_config, platform='weibo', max_queue_size=10000):
    self.base_queue = queue.Queue(maxsize=max_queue_size)
    self.analysis_queue = queue.Queue(maxsize=max_queue_size)
    self.trend_queue = queue.Queue(maxsize=max_queue_size)
```

---

### 2.10 Kafka生产者 (transmit/kafka_producer.py) ⭐⭐⭐⭐

**代码质量**: 良好

**优点**:
- ✅ 异步发送，不阻塞主流程
- ✅ 回调机制，记录成功/失败统计
- ✅ 序列化配置合理

**问题诊断**:

#### 🟡 中等问题1: 缺少消息确认机制
```python
# 当前代码 (kafka_producer.py:40-52)
def send(self, topic: str, message: dict, key: Optional[str] = None):
    if not self.producer:
        logger.warning(f"Kafka 未就绪，丢弃消息")
        return
    
    try:
        future = self.producer.send(topic, key=key, value=message)
        future.add_callback(self._on_send_success)
        future.add_errback(self._on_send_error)
    except KafkaError as e:
        logger.error(f"发送 Kafka 消息失败: {e}")

# 问题: 
# 1. 没有等待消息确认，可能丢失
# 2. 失败后没有重试
# 3. 没有死信队列机制

# 建议: 增加同步发送选项
def send_sync(self, topic: str, message: dict, key: Optional[str] = None, timeout: float = 10.0) -> bool:
    """同步发送消息（确保可靠性）"""
    if not self.producer:
        logger.warning(f"Kafka 未就绪")
        return False
    
    try:
        future = self.producer.send(topic, key=key, value=message)
        metadata = future.get(timeout=timeout)
        logger.debug(f"消息发送成功: {metadata.topic}:{metadata.partition}:{metadata.offset}")
        return True
    except Exception as e:
        logger.error(f"同步发送失败: {e}")
        return False
```

#### 🟢 优化建议2: 增加重试队列
```python
# 建议: 失败消息进入重试队列
class KafkaProducerWrapper:
    def __init__(self, kafka_servers):
        self.retry_queue = queue.Queue(maxsize=1000)
        self._start_retry_worker()
    
    def _start_retry_worker(self):
        """启动重试工作线程"""
        def retry_worker():
            while True:
                try:
                    msg = self.retry_queue.get(timeout=1)
                    self.send(**msg)
                except queue.Empty:
                    pass
        
        thread = threading.Thread(target=retry_worker, daemon=True)
        thread.start()
```

---

## 三、数据库设计Review

### 3.1 表结构设计 ⭐⭐⭐⭐

**优点**:
- ✅ **范式设计合理**: base/analysis/trend 三表分离
- ✅ **索引设计完善**: 主键、外键、联合索引齐全
- ✅ **字段类型合理**: 使用 bigint 存储时间戳，varchar 长度适中
- ✅ **注释完整**: 每个字段都有清晰的注释

**问题诊断**:

#### 🟡 中等问题1: weibo_trend 表缺少分区
```sql
-- 当前表结构 (social_platforms_analysis.sql:216-227)
CREATE TABLE `weibo_trend` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `item_id` varchar(32) NOT NULL,
  `rank_pos` int(11) NOT NULL,
  `heat` bigint(20) NOT NULL,
  `crawl_time` bigint(20) NOT NULL,
  PRIMARY KEY (`id`),
  INDEX `idx_item_time`(`item_id`, `crawl_time`),
  INDEX `idx_crawl_time`(`crawl_time`)
) ENGINE = InnoDB;

-- 问题: 
-- 1. trend表数据量大，查询性能会下降
-- 2. 缺少数据归档策略

-- 建议: 按时间分区
CREATE TABLE `weibo_trend` (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `item_id` varchar(32) NOT NULL,
  `rank_pos` int(11) NOT NULL,
  `heat` bigint(20) NOT NULL,
  `crawl_time` bigint(20) NOT NULL,
  PRIMARY KEY (`id`, `crawl_time`),
  INDEX `idx_item_time`(`item_id`, `crawl_time`),
  INDEX `idx_crawl_time`(`crawl_time`)
) ENGINE = InnoDB
PARTITION BY RANGE (crawl_time) (
    PARTITION p202601 VALUES LESS THAN (UNIX_TIMESTAMP('2026-02-01') * 1000),
    PARTITION p202602 VALUES LESS THAN (UNIX_TIMESTAMP('2026-03-01') * 1000),
    PARTITION p202603 VALUES LESS THAN (UNIX_TIMESTAMP('2026-04-01') * 1000),
    PARTITION pmax VALUES LESS THAN MAXVALUE
);
```

#### 🟡 中等问题2: 缺少数据归档策略
```sql
-- 建议: 创建归档表
CREATE TABLE `weibo_trend_archive` LIKE `weibo_trend`;

-- 定期归档脚本（保留最近30天数据）
INSERT INTO weibo_trend_archive
SELECT * FROM weibo_trend
WHERE crawl_time < UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY)) * 1000;

DELETE FROM weibo_trend
WHERE crawl_time < UNIX_TIMESTAMP(DATE_SUB(NOW(), INTERVAL 30 DAY)) * 1000;
```

---

## 四、性能优化建议

### 4.1 数据库性能优化

#### 🟢 建议1: 增加连接池
```python
# 当前: 每个线程独立连接
# 优化: 使用连接池（DBUtils 或 SQLAlchemy）

# 安装依赖
pip install DBUtils

# 修改 mysql_client.py
from dbutils.pooled_db import PooledDB

class MySQLClient:
    __pool = None
    
    @classmethod
    def get_pool(cls, config):
        if cls.__pool is None:
            cls.__pool = PooledDB(
                creator=pymysql,
                maxconnections=20,
                **config
            )
        return cls.__pool
```

#### 🟢 建议2: 批量插入优化
```python
# 当前: executemany 批量插入
# 优化: 使用 LOAD DATA INFILE（性能提升10倍+）

def batch_write_trend_fast(self, items: List[Dict]) -> int:
    """使用 LOAD DATA INFILE 快速导入"""
    import tempfile
    
    # 1. 写入临时文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        for item in items:
            f.write(f"{item['item_id']}\t{item['rank_pos']}\t{item['heat']}\t{item['crawl_time']}\n")
        temp_file = f.name
    
    # 2. 导入数据库
    try:
        sql = f"""
            LOAD DATA LOCAL INFILE '{temp_file}'
            INTO TABLE {self.table_trend}
            FIELDS TERMINATED BY '\\t'
            (item_id, rank_pos, heat, crawl_time)
        """
        with self.connection.cursor() as cursor:
            cursor.execute(sql)
            self.connection.commit()
            return cursor.rowcount
    finally:
        os.unlink(temp_file)
```

### 4.2 Redis性能优化

#### 🟢 建议1: Pipeline批量操作
```python
# 当前已使用 Pipeline，但可以进一步优化
def update_rank(self, items: List, platform: str = 'weibo') -> bool:
    try:
        zset_key = f"{platform}:realtime_rank"
        pipeline = self.client.pipeline(transaction=False)  # 非事务模式更快
        
        pipeline.delete(zset_key)
        for item in items:
            pipeline.zadd(zset_key, {item.item_id: item.heat})
        
        pipeline.expire(zset_key, 600)
        pipeline.execute()  # 一次网络往返
        return True
    except Exception as e:
        logger.error(f"更新Redis失败: {e}")
        return False
```

### 4.3 爬虫性能优化

#### 🟢 建议1: 异步爬虫
```python
# 当前: 同步爬虫，每次请求阻塞
# 优化: 使用 aiohttp 异步爬虫

import aiohttp
import asyncio

async def fetch_page(session, url, headers):
    async with session.get(url, headers=headers, timeout=10) as response:
        return await response.text()

async def get_realtime_data_async():
    async with aiohttp.ClientSession() as session:
        html = await fetch_page(session, url, headers)
        # 解析逻辑...
        return items

# 主程序调用
items = asyncio.run(get_realtime_data_async())
```

---

## 五、安全性Review

### 5.1 敏感信息管理 ⭐⭐⭐⭐

**优点**:
- ✅ 使用 `.env` 文件管理敏感配置
- ✅ `.gitignore` 已排除 `.env` 文件
- ✅ 使用 `python-dotenv` 加载环境变量

**改进建议**:

#### 🔴 严重问题1: 日志中可能泄露敏感信息
```python
# 当前代码 (getRealtimeWithCrawler.py:34)
logger.info(response.headers.get('Cookie', '未知内容类型'))

# 问题: 可能打印出敏感的 Cookie 信息
# 建议: 移除或脱敏
logger.debug(f"响应状态: {response.status_code}")
```

#### 🟡 中等问题2: API密钥明文存储
```python
# 当前: API密钥明文存储在 .env
# 建议: 使用加密存储

from cryptography.fernet import Fernet

class SecureConfig:
    def __init__(self, key: bytes):
        self.cipher = Fernet(key)
    
    def encrypt(self, plaintext: str) -> bytes:
        return self.cipher.encrypt(plaintext.encode())
    
    def decrypt(self, ciphertext: bytes) -> str:
        return self.cipher.decrypt(ciphertext).decode()

# 使用示例
secure = SecureConfig(key_from_env)
api_key = secure.decrypt(encrypted_api_key_from_env)
```

---

## 六、代码规范Review

### 6.1 PEP 8 规范 ⭐⭐⭐⭐

**优点**:
- ✅ 命名规范：类名大驼峰，函数名小写下划线
- ✅ 导入顺序：标准库 → 第三方库 → 本地模块
- ✅ 缩进统一：使用4个空格

**改进建议**:

#### 🟢 建议1: 使用 Black 自动格式化
```bash
# 安装 Black
pip install black

# 格式化代码
black common/ main.py

# 配置 pyproject.toml
[tool.black]
line-length = 100
target-version = ['py310']
```

#### 🟢 建议2: 使用 Pylint 静态检查
```bash
# 安装 Pylint
pip install pylint

# 检查代码
pylint common/ main.py

# 生成配置文件
pylint --generate-rcfile > .pylintrc
```

---

## 七、测试覆盖Review

### 7.1 单元测试 ⭐⭐⭐

**现状**:
- ✅ 有测试文件 `test_crawler.py`, `test_integration.py`
- ❌ 测试覆盖率不足
- ❌ 缺少 Mock 测试

**改进建议**:

#### 🟢 建议1: 增加单元测试
```python
# test/test_cleaner.py
import pytest
from common.process.cleaner import Cleaner
from common.models.item import HotSearchItem

def test_clean_removes_whitespace():
    cleaner = Cleaner()
    item = HotSearchItem(
        rank=1,
        title="  测试标题  ",
        url="  https://weibo.com  ",
        heat=100,
        latest_crawl_time=1234567890
    )
    cleaned = cleaner.clean([item])
    assert cleaned[0].title == "测试标题"
    assert cleaned[0].url == "https://weibo.com"

def test_clean_filters_empty_title():
    cleaner = Cleaner()
    item = HotSearchItem(
        rank=1,
        title="  ",
        url="https://weibo.com",
        heat=100,
        latest_crawl_time=1234567890
    )
    cleaned = cleaner.clean([item])
    assert len(cleaned) == 0
```

#### 🟢 建议2: 使用 Mock 测试外部依赖
```python
# test/test_llm_client.py
from unittest.mock import Mock, patch
from common.process.llm_client import LLMClient

@patch('requests.post')
def test_chat_success(mock_post):
    # Mock API 响应
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        'choices': [{'message': {'content': '{"sentiment_score": 0.5}'}}]
    }
    mock_post.return_value = mock_response
    
    # 测试
    client = LLMClient({'primary': {'api_url': '...', 'api_key': '...', 'model': '...'}})
    result = client.chat([{'role': 'user', 'content': 'test'}])
    
    assert result == '{"sentiment_score": 0.5}'
    mock_post.assert_called_once()
```

---

## 八、文档与注释Review

### 8.1 代码注释 ⭐⭐⭐⭐

**优点**:
- ✅ 模块级注释完整（模块名称、职责）
- ✅ 关键函数有文档字符串
- ✅ 复杂逻辑有行内注释

**改进建议**:

#### 🟢 建议1: 增加 API 文档
```python
# 使用 Sphinx 生成 API 文档

# 1. 安装依赖
pip install sphinx sphinx-rtd-theme

# 2. 初始化文档
cd docs
sphinx-quickstart

# 3. 生成文档
sphinx-apidoc -o source ../common
make html
```

---

## 九、面试考点总结

### 9.1 架构设计考点

**问题1**: 为什么采用队列+守护线程模式？
```
答案要点:
1. 解耦: 主线程不阻塞，提高吞吐量
2. 削峰: 批量写入减少数据库压力
3. 可靠性: 队列缓冲，防止数据丢失
4. 扩展性: 可增加消费者线程提高处理能力

时间复杂度: 入队O(1)，批量写入O(n)
空间复杂度: O(n) 队列大小
```

**问题2**: 如何保证数据一致性？
```
答案要点:
1. MySQL事务: 批量写入失败时回滚
2. Redis Pipeline: 原子性操作
3. Kafka ACK: 消息确认机制
4. 幂等性设计: INSERT IGNORE / ON DUPLICATE KEY UPDATE
```

### 9.2 性能优化考点

**问题3**: 如何优化数据库写入性能？
```
答案要点:
1. 批量插入: executemany / LOAD DATA INFILE
2. 连接池: 复用连接，减少开销
3. 索引优化: 联合索引、覆盖索引
4. 分区表: 按时间分区，提高查询性能
5. 异步写入: 队列缓冲，削峰填谷
```

### 9.3 故障处理考点

**问题4**: LLM服务不可用时如何处理？
```
答案要点:
1. 故障转移: 主备模型自动切换
2. 降级策略: 返回默认值，保证流程继续
3. 熔断机制: 快速失败，防止雪崩
4. 重试策略: 指数退避，避免加重负载
```

---

## 十、优化优先级清单

### 🔴 高优先级（必须修复）

1. **增加MySQL连接池** - 避免连接耗尽
2. **爬虫增加重试机制** - 提高数据采集可靠性
3. **完善数据清洗逻辑** - 过滤异常数据
4. **增加优雅退出机制** - 防止数据丢失

### 🟡 中优先级（建议优化）

5. **Redis连接池配置** - 提高并发性能
6. **Kafka消息确认机制** - 保证消息可靠性
7. **数据库表分区** - 提高查询性能
8. **增加单元测试** - 提高代码质量

### 🟢 低优先级（可选优化）

9. **异步爬虫改造** - 提高爬取效率
10. **使用dataclass** - 简化数据模型
11. **增加监控指标** - 提高可观测性
12. **API文档生成** - 提高可维护性

---

## 十一、总结与评分

### 总体评分: ⭐⭐⭐⭐ (4.2/5.0)

**优势**:
- ✅ 架构设计优秀，职责分离清晰
- ✅ 核心模块代码质量高（LLM分析、异步写入）
- ✅ 异常处理完善，日志记录充分
- ✅ 配置管理规范，敏感信息保护到位

**待改进**:
- ⚠️ 数据库连接管理需优化（连接池）
- ⚠️ 爬虫模块需增强可靠性（重试、限流）
- ⚠️ 数据清洗逻辑需完善（去重、验证）
- ⚠️ 测试覆盖率需提高

**面试竞争力**:
- 🎯 架构设计能力: ⭐⭐⭐⭐⭐
- 🎯 代码质量: ⭐⭐⭐⭐
- 🎯 性能优化: ⭐⭐⭐⭐
- 🎯 工程实践: ⭐⭐⭐⭐

---

## 附录：关键知识点记录

### A. Python高级特性

#### 1. @property 装饰器
```python
# 作用: 将方法变成属性调用，实现延迟计算
# 优势: 
# 1. 惰性求值，提高性能
# 2. 封装实现细节
# 3. 保持接口一致性

class HotSearchItem:
    @property
    def item_id(self) -> str:
        if self._item_id is None:
            self._item_id = hashlib.md5(self.title.encode()).hexdigest()
        return self._item_id
```

#### 2. 队列+守护线程模式
```python
# 作用: 实现异步处理，解耦生产者和消费者
# 优势:
# 1. 提高吞吐量
# 2. 削峰填谷
# 3. 故障隔离

import queue, threading

q = queue.Queue(maxsize=1000)

def worker():
    while True:
        item = q.get()
        process(item)
        q.task_done()

threading.Thread(target=worker, daemon=True).start()
```

### B. 中间件交互机制

#### 1. MySQL批量写入优化
```python
# executemany 原理:
# 1. 将多个INSERT语句合并成一个
# 2. 减少网络往返次数
# 3. 事务一次性提交

# 性能对比:
# 单条插入: 1000条 × 10ms = 10秒
# 批量插入: 1次 × 100ms = 0.1秒
# 性能提升: 100倍
```

#### 2. Redis Pipeline机制
```python
# Pipeline 原理:
# 1. 将多个命令打包发送
# 2. 一次网络往返执行所有命令
# 3. 减少RTT（Round-Trip Time）

# 性能对比:
# 单条操作: 100条 × 1ms = 100ms
# Pipeline: 1次 × 5ms = 5ms
# 性能提升: 20倍
```

#### 3. Kafka消息可靠性
```python
# ACK配置:
# acks=0: 不等待确认（最快，可能丢失）
# acks=1: 等待Leader确认（默认，平衡）
# acks=all: 等待所有副本确认（最慢，最可靠）

# 推荐配置:
producer = KafkaProducer(
    acks=1,  # 平衡性能和可靠性
    retries=3,  # 重试3次
    enable.idempotence=True  # 幂等性，防止重复
)
```

---

**Review完成时间**: 2026年5月8日  
**下次Review建议**: 3个月后或重大版本更新时
