import pymysql
from datetime import datetime

from common.config.settings import MYSQL_CONFIG
from common.models.item import HotSearchItem
from common.utils.logging_config import logger

class MySQLClient:
    def __init__(self,platform: str):
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

            # 【核心修改】：在初始化时，将配置里的表名缓存为实例属性
            self.table_current = MYSQL_CONFIG[platform]['chs']
            self.table_history = MYSQL_CONFIG[platform]['hhs']

            logger.info(f"MySQL 连接成功！当前目标表: {self.table_current}, {self.table_history}")
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            raise

    def save_to_history(self, items: list[HotSearchItem]):
        """
        【历史表策略】：只增不减 (Append-Only)
        """
        if not items:
            return

        # 使用 f-string 动态拼接表名，并加上反引号(``)防止 SQL 关键字冲突
        sql = f"""
            INSERT INTO `{self.table_history}` 
            (rank_position, title, url, heat, latest_crawl_time, first_on_board_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params_list = self._prepare_params(items)

        try:
            with self.connection.cursor() as cursor:
                cursor.executemany(sql, params_list)
            logger.debug(f"成功追加 {len(items)} 条数据到 {self.table_history} 表")
        except Exception as e:
            logger.error(f"写入历史流水表失败: {e}")

    def save_to_current(self, items: list[HotSearchItem]):
        """
        【当前表策略】：暴力清空 + 全量插入 (Truncate & Insert)
        """
        if not items:
            logger.warning("当前表写入操作收到空数据列表，跳过写入。")
            return

        # 动态拼接表名
        truncate_sql = f"TRUNCATE TABLE `{self.table_current}`;"
        insert_sql = f"""
            INSERT INTO `{self.table_current}` 
            (rank_position, title, url, heat, latest_crawl_time, first_on_board_time)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        params_list = self._prepare_params(items)

        try:
            with self.connection.cursor() as cursor:
                # 第一步：物理级瞬间清空旧榜单
                cursor.execute(truncate_sql)

                # 第二步：毫无负担地顺序写入新榜单
                cursor.executemany(insert_sql, params_list)

            logger.debug(f"成功重置并写入了 {len(items)} 条数据到 {self.table_current} 表")
        except Exception as e:
            logger.error(f"重置当前快照表失败: {e}")

    def _prepare_params(self, items: list[HotSearchItem]) -> list[tuple]:
        """
        将 Python 对象剥离成 MySQL 需要的元组格式，并转换时间戳。
        """
        params = []
        for item in items:
            dt_latest = datetime.fromtimestamp(item.latest_crawl_time)
            dt_first = datetime.fromtimestamp(item.first_on_board_time)

            params.append((
                item.rank,
                item.title,
                item.url,
                item.heat,
                dt_latest,
                dt_first
            ))
        return params

    def close(self):
        """优雅关闭连接"""
        if self.connection and self.connection.open:
            self.connection.close()
            logger.info("MySQL 连接已断开。")

if __name__ == '__main__':
    # 简单测试连接和写入
    client = MySQLClient()
    test_item = HotSearchItem(
        rank=1,
        title="测试热搜",
        url="https://example.com",
        heat=999999,
        latest_crawl_time=int(datetime.now().timestamp()),
        first_on_board_time=int(datetime.now().timestamp())
    )
    client.save_to_current([test_item])
    client.save_to_history([test_item])
    client.close()