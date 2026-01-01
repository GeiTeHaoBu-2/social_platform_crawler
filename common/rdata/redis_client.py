import time
import json
import hashlib

# Import MySQL backup function
from common.mdata.mysql_client import save_hot_search_to_mysql

__all__ = ['save_hot_search_to_redis']

# Try to import redis; if unavailable, we'll fall back to MySQL-only behavior
try:
    import redis
    _has_redis = True
except Exception:
    redis = None
    _has_redis = False

r = None
if _has_redis:
    try:
        # 连接Redis（根据实际情况修改 host/port/password 或使用环境变量）
        # decode_responses=True 使返回值为 str，便于调试和打印
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    except Exception:
        r = None


def _make_key(title: str) -> str:
    """生成一个安全的 Redis key，避免 title 太长或包含特殊字符"""
    h = hashlib.md5(title.encode('utf-8')).hexdigest()
    return f"weibo:hot:{h}"


def save_hot_search_to_redis(hot_search):
    """
    如果 Redis 可用，则保存热搜到 Redis（以 hash 结构保存每条热搜的字段），
    并将数据备份到 MySQL。
    如果 Redis 不可用，则直接写入 MySQL 作为降级策略。
    hot_search: dict 包含 title, hot_count, tag, url, first_crawled, rank
    """
    raw_title = hot_search.get('title', '')
    if not raw_title:
        raise ValueError("hot_search 必须包含 title 字段")

    # 如果 redis 不可用，降级为只保存到 MySQL
    if not _has_redis or r is None:
        print("⚠️ Redis 未安装或不可用，降级为仅写入 MySQL 备份")
        save_hot_search_to_mysql(hot_search)
        return

    key = _make_key(raw_title)

    # 将所有要存的字段先转换为字符串，避免类型问题
    fields = {
        'title': raw_title,
        'rank': str(hot_search.get('rank', '')),
        'hot_count': str(hot_search.get('hot_count', '')),
        'tag': str(hot_search.get('tag', '')),
        'url': str(hot_search.get('url', '')),
        'first_crawled': str(hot_search.get('first_crawled', time.time())),
        'update_time': str(time.time())
    }

    try:
        existed_before = bool(r.exists(key))
        pipe = r.pipeline()
        # hset with mapping is available, but use individual hset for compatibility
        for field, value in fields.items():
            pipe.hset(key, field, value)
        # 可选：设置一个 TTL，例如 7 天（按需启用）
        # pipe.expire(key, 7 * 24 * 3600)
        pipe.execute()

        if existed_before:
            print(f"✅ 更新热搜: {raw_title} (热度: {fields['hot_count']})")
        else:
            print(f"✅ 新增热搜: {raw_title} (热度: {fields['hot_count']})")

        # 备份到 MySQL（非阻塞调用可改为异步/队列）
        try:
            save_hot_search_to_mysql(hot_search)
        except Exception as e:
            # MySQL 备份失败应该记录日志，但不应影响主流程
            print(f"保存到 MySQL 失败: {e}")

    except redis.RedisError as e:
        # 捕获 redis 客户端异常并抛出友好信息
        print(f"Redis 操作失败: {e}")
        # 降级：尝试写 MySQL
        try:
            save_hot_search_to_mysql(hot_search)
        except Exception as ex:
            print(f"Redis 和 MySQL 均保存失败: {ex}")
        raise


if __name__ == "__main__":
    # 本地测试用例
    test = {
        'rank': 1,
        'title': '示例',
        'hot_count': '1万',
        'tag': '新',
        'url': 'https://example.com',
        'first_crawled': time.time()
    }
    save_hot_search_to_redis(test)
