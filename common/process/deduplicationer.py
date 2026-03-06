import json
import redis
from typing import List
from common.models.item import HotSearchItem
from common.config.settings import REDIS_CONFIG
from common.utils.logging_config import logger



class Deduplicationer:
    def __init__(self):
        """
        初始化增量路由器，连接指定的 Deduplication 状态库 (DB 1)。
        """
        try:
            # 【关键修改】：从配置获取 deduplication_db (1)
            target_db = REDIS_CONFIG.get('deduplication_db', 1)

            self.redis_client = redis.Redis(
                host=REDIS_CONFIG.get('host', '127.0.0.1'),
                port=REDIS_CONFIG.get('port', 6379),
                db=target_db,
                password=REDIS_CONFIG.get('password', None),
                decode_responses=True
            )

            # 业务阈值配置
            self.heat_threshold = 5000  # 热度变化 > 5000 触发
            self.state_ttl = 86400  # 24小时记忆周期

            logger.info(f"Deduplicationer 已就绪，正在监控 Redis 数据库: {target_db}")
        except Exception as e:
            logger.error(f"Deduplicationer 连接 Redis 失败: {e}")
            raise

    def deduplicate(self, new_items: List[HotSearchItem], platform: str = 'weibo') -> List[HotSearchItem]:
        """
        比对当前榜单与状态库记忆，筛选出需要发往 Kafka/MySQL 的增量数据。
        """
        if not new_items:
            return []

        incremental_items = []

        # 状态 Key 规范：platform:state:title
        keys = [f"{platform}:state:{item.title}" for item in new_items]

        # 1. 批量唤醒记忆 (DB 1)
        old_states_raw = self.redis_client.mget(keys)
        pipeline = self.redis_client.pipeline()

        # 2. 状态 Diff 计算
        for item, key, old_state_json in zip(new_items, keys, old_states_raw):
            is_incremental = False

            if old_state_json is None:
                # 场景 A：完全新话题
                is_incremental = True
            else:
                # 场景 B：老话题，进行阈值判断
                try:
                    old_state = json.loads(old_state_json)
                    # 继承血统：初次上榜时间
                    item.first_on_board_time = old_state.get('first_on_board_time', item.first_on_board_time)

                    old_heat = old_state.get('heat', 0)
                    old_rank = old_state.get('rank', 0)

                    # 触发规则：排名变动 OR 热度波动超过阈值
                    if item.rank != old_rank or abs(item.heat - old_heat) > self.heat_threshold:
                        is_incremental = True

                except json.JSONDecodeError:
                    is_incremental = True

            if is_incremental:
                incremental_items.append(item)

            # 3. 刷新状态并续命 (SETEX 命令进入 Pipeline)
            pipeline.setex(
                name=key,
                time=self.state_ttl,
                value=json.dumps(item.to_dict(), ensure_ascii=False)
            )

        # 4. 一次性提交更新
        try:
            pipeline.execute()
        except Exception as e:
            logger.error(f"批量刷新状态库失败: {e}")

        return incremental_items