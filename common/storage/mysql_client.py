import pymysql
import hashlib
from datetime import datetime

from common.config.settings import MYSQL_CONFIG
from common.models.item import HotSearchItem
from common.utils.logging_config import logger


class MySQLClient:
    def __init__(self, platform: str):
        """
        初始化 MySQL 客户端，自动读取配置并绑定表名。
        """
        try:
            self.connection = pymysql.connect(
                host=MYSQL_CONFIG['host'],
                port=MYSQL_CONFIG['port'],
                user=MYSQL_CONFIG['user'],
                password=MYSQL_CONFIG['password'],
                database=MYSQL_CONFIG['database'],
                charset=MYSQL_CONFIG['charset'],
                autocommit=True
            )

            self.platform = platform
            # 【核心修改】：自动推导新架构下的三张基础表名 (不含 Flink 写入的两张分析表)
            # 例如平台传入 'weibo'，则表名为 'weibo_base', 'weibo_trend', 'weibo_current'
            self.table_base = f"{platform}_base"
            self.table_trend = f"{platform}_trend"
            self.table_current = f"{platform}_current"

            logger.info(f"MySQL 连接成功！目标核心表: {self.table_base}, {self.table_trend}, {self.table_current}")
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            raise

    def save_incremental_data(self, items: list[HotSearchItem]):
        """
        【历史双表写入策略】：
        1. 基础表 (Base): 存在即忽略 (INSERT IGNORE)
        2. 趋势流水表 (Trend): 无脑追加 (Append-Only)
        """
        if not items:
            return

        # 准备数据：在存入数据库前，现场计算 MD5 生成 item_id
        base_params = []
        trend_params = []

        for item in items:
            # 现场生成脱离业务且无歧义的数据库主键：MD5(title)
            item_id = hashlib.md5(item.title.encode('utf-8')).hexdigest()

            # 组装 weibo_base 表数据
            base_params.append((
                item_id,
                item.title,
                item.url,
                item.first_on_board_time
            ))

            # 组装 weibo_trend 表数据
            trend_params.append((
                item_id,
                item.rank,
                item.heat,
                item.latest_crawl_time
            ))

        # 【SQL 1：基础表】使用 INSERT IGNORE
        sql_base = f"""
            INSERT IGNORE INTO `{self.table_base}` 
            (item_id, title, url, first_time)
            VALUES (%s, %s, %s, %s)
        """

        # 【SQL 2：趋势表】无脑插入
        sql_trend = f"""
            INSERT INTO `{self.table_trend}` 
            (`item_id`, `rank_pos`, `heat`, `crawl_time`)
            VALUES (%s, %s, %s, %s)
        """

        try:
            with self.connection.cursor() as cursor:
                # 执行双写
                cursor.executemany(sql_base, base_params)
                cursor.executemany(sql_trend, trend_params)

            logger.debug(f"成功双写 {len(items)} 条增量数据到 {self.platform} 基础与趋势表。")
        except Exception as e:
            logger.error(f"写入历史双表架构失败: {e}")

    def save_to_current(self, items: list[HotSearchItem]):
        """
        【快照表策略】：暴力清空 + 全量插入 (Truncate & Insert)
        作为 Redis 的物理级兜底备份。
        """
        if not items:
            return

        truncate_sql = f"TRUNCATE TABLE `{self.table_current}`;"

        insert_sql = f"""
            INSERT INTO `{self.table_current}` 
            (`item_id`, `rank_pos`, `title`, `url`, `heat`, `crawl_time`)
            VALUES (%s, %s, %s, %s, %s, %s)
        """

        params = []
        for item in items:
            item_id = hashlib.md5(item.title.encode('utf-8')).hexdigest()
            params.append((
                item_id,
                item.rank,
                item.title,
                item.url,
                item.heat,
                item.latest_crawl_time
            ))

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(truncate_sql)
                cursor.executemany(insert_sql, params)
            logger.debug(f"容灾备份：已刷新 {len(items)} 条快照到 {self.table_current} 表")
        except Exception as e:
            logger.error(f"重置当前快照表失败: {e}")

    def close(self):
        """优雅关闭连接"""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("MySQL 连接已断开。")


if __name__ == '__main__':
    # 简单测试写入
    client = MySQLClient(platform='weibo')
    test_item = HotSearchItem(
        rank=1,
        title="科幻电影定档",
        url="https://weibo.com/test",
        heat=5000000,
        latest_crawl_time=int(datetime.now().timestamp()),
        first_on_board_time=int(datetime.now().timestamp())
    )

    # 1. 测试写入容灾快照表
    client.save_to_current([test_item])
    # 2. 测试写入基础信息表和趋势流水表
    client.save_incremental_data([test_item])

    client.close()