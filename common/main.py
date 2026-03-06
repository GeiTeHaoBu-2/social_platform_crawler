from time import sleep

from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.deduplicationer import Deduplicationer
from common.storage.mysql_client import MySQLClient
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.config.settings import KAFKA_CONFIG
from common.utils.logging_config import logger
from common.storage.redis_client import save_hot_search_to_redis

# 初始化各个组件
cleaner = Cleaner()
deduplicationer = Deduplicationer()
kafka_producer = KafkaProducerWrapper(KAFKA_CONFIG['servers'])
weibo_mysql_client = MySQLClient('weibo_table')


def hotSearchCrawler():
    logger.info("======= 微博热搜监控流水线启动 =======")

    # 1. 爬取原始数据 (得到的是 HotSearchItem 对象列表)
    raw_data_items = get_realtime_data()
    if not raw_data_items:
        logger.warning("本次未抓取到数据，流水线中止。")
        return
    logger.info(f"1. 成功爬取到 {len(raw_data_items)} 条热搜对象")

    # 2. 数据清洗 (过滤标题乱码、空格等)
    cleaned_items = cleaner.clean(raw_data_items)
    logger.info(f"2. 数据清洗完成，剩余 {len(cleaned_items)} 条有效数据")

    # 3. 更新实时大屏快照 (Redis DB 0 & MySQL Current Table)
    # 这两处是“覆盖式”更新，所以直接用 cleaned_items 全量覆盖
    try:
        # 刷新 Redis 大屏缓存 (DB 0)
        save_hot_search_to_redis(cleaned_items, 'weibo')
        # 刷新 MySQL 当前快照表 (Truncate & Insert)
        weibo_mysql_client.save_to_current(cleaned_items)
        logger.info("3. 实时快照已成功刷新至 Redis(DB 0) 和 MySQL(Current)")
    except Exception as e:
        logger.error(f"3. 快照更新失败: {e}")

    # 4. 增量比对 (核心：对比 Redis DB 1 中的长期记忆，计算状态差值)
    # 这一步执行完后，cleaned_items 里的 item 会自动继承旧的 first_on_board_time
    unique_items = deduplicationer.deduplicate(cleaned_items, platform='weibo')
    logger.info(f"4. 增量比对完成：共发现 {len(unique_items)} 条 [新上榜/热度跃迁/排名变动] 数据")

    # 5. 持久化增量数据 & 发送消息队列
    if not unique_items:
        logger.info("5. 本次抓取无实质性变动，跳过持久化与发送。")
        return

    try:
        # 【重要】：只将“有变动”的数据追加到历史表，形成热度走势线
        weibo_mysql_client.save_to_history(unique_items)
        logger.info(f"5. 已将 {len(unique_items)} 条增量记录追加至 MySQL 历史表")

        # 将增量推送到 Kafka 供 Flink 消费
        #for item in unique_items:
        #    kafka_producer.send(KAFKA_CONFIG['topics']['weibo'], item.to_dict())
        #    logger.info(f"   [Kafka 发送成功] -> {item.title} (热度: {item.heat})")

    except Exception as e:
        logger.error(f"5. 增量下发流程出错: {e}")


if __name__ == "__main__":
    try:
        while True:
            hotSearchCrawler()
            sleep(10)  # 每分钟执行一次
    finally:
        # 保证程序退出时关闭连接
        weibo_mysql_client.close()