# 爬虫问题排查记录

---

## 1. 热搜标题乱码问题 (2026-04-11)

### 1.1 问题描述

爬虫偶尔会爬取到奇形怪状的标题文字，如：
```
е∞ПйїДж≤єзЊОеЉП еЕ®еЖ∞еОїж∞і
```

### 1.2 问题原因

**字符编码处理错误**

原代码使用 `response.apparent_encoding` 自动检测编码：
```python
response.encoding = response.apparent_encoding  # 自动判断编码
```

`apparent_encoding` 使用 `chardet` 库猜测编码，存在以下问题：
- 准确率不是 100%
- 当网页内容较短或包含特殊字符时可能误判
- 微博热搜页面编码应为 `utf-8`，但可能被误判为 `gb2312`、`gbk` 等

### 1.3 解决方案

**强制指定 utf-8 编码**：
```python
response.encoding = 'utf-8'
```

### 1.4 修改文件

| 文件 | 修改内容 |
|------|---------|
| `common/platforms/sina/getRealtimeWithCrawler.py` | 第 28 行，将 `apparent_encoding` 改为 `'utf-8'` |

### 1.5 修改前后对比

**修改前**：
```python
response.encoding = response.apparent_encoding  # 自动判断编码，避免乱码
```

**修改后**：
```python
response.encoding = 'utf-8'
```

### 1.6 其他可选方案

如果强制 utf-8 仍有问题，可尝试：
```python
# 方案2：使用 response.content 让 BeautifulSoup 自动处理编码
soup = BeautifulSoup(response.content, 'lxml')
```

---

## 2. trend 表数据丢失问题 (2026-05-05)

### 2.1 问题描述

- Python 启动时 MySQL 未启动
- 启动 MySQL 后，只有部分热搜有 trend 数据
- 运行 10 分钟后，大部分热搜仍无 trend 数据

### 2.2 问题原因

**async_writer 线程 MySQL 连接失败后直接终止，不重试**

原代码：
```python
def _trend_writer_loop(self):
    try:
        self._trend_mysql_client = MySQLClient(self.db_config, self.platform)
        logger.info("[TrendWriter] MySQL连接已创建")
    except Exception as e:
        logger.error(f"[TrendWriter] MySQL连接创建失败: {e}")
        return  # 直接返回，线程终止
```

**问题链条**：
1. Python 启动时 MySQL 未启动
2. TrendWriter 线程尝试连接 MySQL 失败
3. 线程直接终止（`return`）
4. 后续所有 trend 数据入队，但没有消费者线程
5. 队列数据堆积，最终丢失

### 2.3 解决方案

**添加 MySQL 连接重试机制**：
```python
def _trend_writer_loop(self):
    max_retries = 5
    retry_interval = 5
    
    for retry in range(max_retries):
        try:
            self._trend_mysql_client = MySQLClient(self.db_config, self.platform)
            logger.info("[TrendWriter] MySQL连接已创建")
            break
        except Exception as e:
            logger.error(f"[TrendWriter] MySQL连接创建失败 (尝试 {retry + 1}/{max_retries}): {e}")
            if retry < max_retries - 1:
                logger.info(f"[TrendWriter] {retry_interval}秒后重试...")
                time.sleep(retry_interval)
            else:
                logger.error("[TrendWriter] 达到最大重试次数，线程终止")
                return
```

### 2.4 修改内容

| 文件 | 修改内容 |
|------|---------|
| `common/storage/async_writer.py` | `_base_writer_loop()`、`_analysis_writer_loop()`、`_trend_writer_loop()` 添加重试机制 |
| `common/storage/mysql_client.py` | `batch_write_trend()` 日志级别从 `debug` 改为 `info` |

### 2.5 重试策略

| 参数 | 值 | 说明 |
|------|-----|------|
| `max_retries` | 5 | 最大重试次数 |
| `retry_interval` | 5 | 重试间隔（秒） |

### 2.6 日志改进

成功写入日志从 `logger.debug` 改为 `logger.info`，便于观察：
```python
# 修改前
logger.debug(f"成功写入 {len(items)} 条数据到 {self.table_trend} 表")

# 修改后
logger.info(f"成功写入 {len(items)} 条数据到 {self.table_trend} 表")
```
