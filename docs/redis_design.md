# Redis 数据结构设计 - 微博热搜实时榜单

## 📋 两个 Key 的分工

### 1. `{platform}:realtime_rank` (ZSet 有序集合)

```redis
Key: weibo:realtime_rank
Type: ZSet (Sorted Set)
结构: Member(热度值) -> Score(item_id)

示例:
  "abc123..." -> 5000000  # 热度500万
  "def456..." -> 3000000  # 热度300万
  "ghi789..." -> 1000000  # 热度100万
```

**核心职责**: 按热度排序的**索引**

**为什么用 ZSet？**
- ✅ Redis 原生支持按 Score 排序
- ✅ `ZREVRANGE key 0 9` 毫秒级取 Top10
- ✅ `ZRANGEBYSCORE key 1000000 +inf` 范围查询

**如果只用 Hash 会怎样？**
```python
# 悲剧：需要全量加载到内存再排序（O(NlogN)）
all_data = redis.hgetall("platform:weibo:realtime_board")
sorted_data = sorted(all_data.items(), 
                     key=lambda x: x[1]['heat'], 
                     reverse=True)[:10]  # 慢！
```

---

### 2. `platform:{platform}:realtime_board` (Hash 哈希)

```redis
Key: platform:weibo:realtime_board
Type: Hash
结构: Field(item_id) -> Value(JSON字符串)

示例:
  "abc123..." -> '{
    "title": "某某明星结婚",
    "heat": 5000000,
    "url": "https://s.weibo.com/...",
    "rank": 1,
    "first_on_board_time": 1699123456
  }'
```

**核心职责**: 存储完整数据的**数据仓库**

**为什么用 Hash？**
- ✅ 存储任意字段（title, url, heat...）
- ✅ O(1) 快速读取单条数据
- ✅ 便于前端一次性取完整信息

---

## 🎯 设计本质：索引 + 数据分离

类比数据库：

| Redis Key | Redis 类型 | 作用 | 类比数据库 |
|-----------|------------|------|-----------|
| `weibo:realtime_rank` | ZSet | **索引** - 按热度排序快速定位 | `CREATE INDEX ON heat` |
| `platform:weibo:realtime_board` | Hash | **数据** - 存储完整字段 | `SELECT * FROM hot_search` |

类比书本：
- **目录**（ZSet）→ 告诉你第几页是什么内容，按热度排列
- **正文**（Hash）→ 存储完整的文章内容

---

## 💡 实际使用流程

### 场景：前端展示热度榜单 Top 10

```python
# 步骤1：从 ZSet 快速获取排序后的 ID 列表（O(logN)）
ids = redis.zrevrange("weibo:realtime_rank", 0, 9)
# 返回: ["abc123...", "def456...", "ghi789...", ...]

# 步骤2：用 ID 去 Hash 取完整数据（O(1) * 10 = O(1)）
for item_id in ids:
    data = redis.hget("platform:weibo:realtime_board", item_id)
    item = json.loads(data)
    print(f"Rank {i+1}: {item['title']} (热度: {item['heat']})")
```

**性能**: 无论有100条还是10万条，取Top10都是毫秒级！

---

## ❌ 常见误区

**误区**: "Hash 里也有 heat 字段，为什么还要 ZSet？"

**正解**: Hash 确实能存 heat，但 **Redis Hash 不支持按字段值排序查询**！

```redis
# Hash 做不到：
"按 heat 字段排序取前10"  ❌ 不支持
"查询 heat > 100万的条目"  ❌ 不支持

# 只有 ZSet 能做到：
ZREVRANGE weibo:realtime_rank 0 9
ZRANGEBYSCORE weibo:realtime_rank 1000000 +inf
```

---

## 🔧 代码实现位置

| 方法 | 文件 | 职责 |
|------|------|------|
| `update_rank()` | [`redis_manager.py:57-97`](common/storage/redis_manager.py:57-97) | 维护 ZSet 索引 |
| `save_hot_search()` | [`redis_manager.py:99-141`](common/storage/redis_manager.py:99-141) | 维护 Hash 数据 |

---

## 📊 两种方案的对比

| 方案 | 优点 | 缺点 |
|------|------|------|
| **双 Key (当前)** | 查询快，各司其职 | 数据冗余（存了两次 item_id） |
| **单 Hash** | 存储简单 | 排序查询需要全量加载到内存排序 |

**结论**: 实时榜单场景下，查询性能远比存储空间重要，双 Key 设计是最佳选择。

---

## 🎓 知识点总结

1. **ZSet**: 适合需要排序/排名的场景（排行榜、榜单）
2. **Hash**: 适合存储对象/结构体（用户信息、配置项）
3. **组合使用**: 复杂场景往往需要多种数据类型配合
4. **索引思想**: 和数据库一样，Redis 也需要"索引"来加速查询
