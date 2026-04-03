# 调试日志 (Debug Log)

## 2024-04-02 MySQL批量写入错误修复

### 问题现象
运行 `common/main.py` 时报错：
```
[ERROR] - 批量写入 weibo_analysis 失败: not all arguments converted during string formatting
[ERROR] - AsyncWriter批量写入base表失败: (0, '')
[ERROR] - AsyncWriter批量写入analysis表失败: (0, '')
```

### 问题诊断

#### 根本原因
- `batch_write_analysis()` 错误地提供了9个参数
- 但SQL语句中只有5个占位符 `%s`
- 错误理解：以为 `ON DUPLICATE KEY UPDATE` 需要重复提供参数

#### 代码位置
`common/storage/mysql_client.py`

### 修复内容

#### 1. 修复analysis表参数数量

**修复前（错误）**:
```python
params = []
for item in items:
    params.append((
        item['item_id'],
        item['sentiment_score'],
        item['type_name'],
        item['topic_name'],
        item['nlp_time'],
        # 错误：重复提供UPDATE参数
        item['sentiment_score'],
        item['type_name'],
        item['topic_name'],
        item['nlp_time']
    ))
```

**修复后（正确）**:
```python
params = []
for item in items:
    # 注意：使用VALUES()函数在ON DUPLICATE KEY UPDATE中引用插入值
    # 只需要提供INSERT部分的5个参数
    params.append((
        item['item_id'],
        item['sentiment_score'],
        item['type_name'],
        item['topic_name'],
        item['nlp_time']
    ))
```

#### 2. 修复影响行数获取

**修复前（错误）**:
```python
try:
    with self.connection.cursor() as cursor:
        affected = cursor.executemany(sql, params)  # 错误：executemany不直接返回影响行数
        self.connection.commit()
        return affected
```

**修复后（正确）**:
```python
try:
    with self.connection.cursor() as cursor:
        cursor.executemany(sql, params)
        self.connection.commit()
        affected = self.connection.affected_rows()  # 正确：使用connection的方法
        return affected
```

### 关键知识点

#### ON DUPLICATE KEY UPDATE的正确用法
```sql
INSERT INTO table (a, b, c) VALUES (%s, %s, %s)
ON DUPLICATE KEY UPDATE
    a = VALUES(a),  -- 使用VALUES()引用INSERT的值
    b = VALUES(b),
    c = VALUES(c)
```

**重要提示**: 
- 只需要提供INSERT部分的参数
- UPDATE部分使用 `VALUES(column)` 函数引用，**不需要重复提供参数**
- PyMySQL的 `cursor.executemany()` 不返回影响行数，需要使用 `connection.affected_rows()`

### 相关文件
- `common/storage/mysql_client.py` - 修复的文件
- `common/storage/async_writer.py` - 调用方（无需修改）

### 验证方法
重新运行 `common/main.py`，检查是否还有MySQL写入错误：
```bash
python common/main.py
```

预期输出：
```
[INFO] - 成功将 50 条完整数据推送到Kafka
# 不再有 [ERROR] - 批量写入...失败 的日志
```
