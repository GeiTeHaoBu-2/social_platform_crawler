# 该文件已迁移为 redis_client.py，以避免与第三方包名冲突。
# 请将所有导入从 `common.rdata.redis` 改为 `common.rdata.redis_client`。
# 为避免误用，这里直接提示并终止（如果你希望保留兼容代理，可以改为导入并转发）。
raise ImportError(
    "本模块已迁移到 common.rdata.redis_client，为避免与 pypi 包 'redis' 冲突请更新导入："
    " from common.rdata.redis_client import save_hot_search_to_redis"
)

