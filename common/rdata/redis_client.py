import redis
import time
import json

__all__ = ['save_hot_search_to_redis', 'save_to_mysql']

# 连接Redis（根据实际情况修改 host/port/password）
# decode_responses=True 使返回值为 str，便于调试和打印
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)


def save_hot_search_to_redis(hot_search):
    """
    保存热搜到Redis去重表（以热搜标题为key）
    hot_search: dict 包含 title, hot_count, tag, url, first_crawled
    """
    # 给 key 加前缀，避免与其他 key 冲突
    raw_title = hot_search.get('title', '')
    if not raw_title:
        raise ValueError("hot_search 必须包含 title 字段")

    key = f"{raw_title}"

    # 将所有要存的字段先转换为字符串，避免类型问题
    fields = {
        'hot_count': str(hot_search.get('hot_count', '')),
        'tag': str(hot_search.get('tag', '')),
        'url': str(hot_search.get('url', '')),
        'first_crawled': str(hot_search.get('first_crawled', time.time())),
        'update_time': str(time.time())
    }

    try:
        existed_before = bool(r.exists(key))
        # 使用 pipeline 逐字段写入，兼容性最好（避免 mapping 参数在某些环境/版本下导致参数错误）
        pipe = r.pipeline()
        for field, value in fields.items():
            pipe.hset(key, field, value)
        pipe.execute()

        if existed_before:
            print(f"✅ 更新热搜: {raw_title} (热度: {fields['hot_count']})")
        else:
            print(f"✅ 新增热搜: {raw_title} (热度: {fields['hot_count']})")

        # 持久化到 MySQL 或其他业务逻辑
        save_to_mysql(hot_search)

    except redis.RedisError as e:
        # 捕获 redis 客户端异常并抛出友好信息
        print(f"Redis 操作失败: {e}")
        raise


def save_to_mysql(hot_search):
    """
    示例：将热搜保存到MySQL（请用实际的pymysql/SQLAlchemy实现）
    """
    print(f"💾 保存到MySQL: {hot_search['title']} (热度: {hot_search['hot_count']})")


if __name__ == "__main__":
    # 测试用例（仅作快速验证）
    test = {
        'title': '示例',
        'hot_count': '1万',
        'tag': '新',
        'url': 'https://example.com',
        'first_crawled': time.time()
    }
    save_hot_search_to_redis(test)
