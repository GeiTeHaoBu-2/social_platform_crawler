from time import sleep

from common.platforms.sina.getRealtimeWithCrawler import get_realtime_data
from common.process.cleaner import Cleaner
from common.process.deduplicationer import Deduplicationer
from common.storage.mysql_client import MySQLClient
from common.transmit.kafka_producer import KafkaProducerWrapper
from common.config.settings import KAFKA_CONFIG
from common.config.settings import CRAWLER_CONFIG
from common.utils.logging_config import logger
from common.storage.redis_client import save_hot_search_to_redis

# 初始化各个组件
cleaner = Cleaner()
deduplicationer = Deduplicationer()
kafka_producer = KafkaProducerWrapper(KAFKA_CONFIG['servers'])

# 传入精准的平台标识 'weibo'，对接 MySQLClient 新版的三表推导逻辑 (base, trend, current)
weibo_mysql_client = MySQLClient('weibo')


def hotSearchCrawler():
    logger.info("======= 微博热搜监控流水线启动 =======")

    # 1. 爬取原始数据
    raw_data_items = get_realtime_data()
    if not raw_data_items:
        logger.warning("本次未抓取到数据，流水线中止。")
        return
    logger.info(f"1. 成功爬取到 {len(raw_data_items)} 条热搜对象")

    # 2. 数据清洗
    cleaned_items = cleaner.clean(raw_data_items)
    logger.info(f"2. 数据清洗完成，剩余 {len(cleaned_items)} 条有效数据")

    # 3. 刷新实时大屏快照 (双重防线：Redis 高速内存 + MySQL 物理容灾)
    try:
        # 第一防线：更新 Redis (极速)
        save_hot_search_to_redis(cleaned_items, 'weibo')

        # 第二防线：更新 MySQL 快照表 (容灾兜底)
        weibo_mysql_client.save_to_current(cleaned_items)

        logger.info("3. 实时快照已成功刷新至 Redis (高速) 和 MySQL (容灾兜底)")
    except Exception as e:
        logger.error(f"3. 快照更新失败: {e}")

    # 4. 增量比对 (核心：对比 Redis DB 1 中的长期记忆，计算状态差值)
    unique_items = deduplicationer.deduplicate(cleaned_items, platform='weibo')
    logger.info(f"4. 增量比对完成：共发现 {len(unique_items)} 条 [新上榜/热度跃迁/排名变动] 数据")

    # 5. 持久化增量数据 & 发送消息队列
    if not unique_items:
        logger.info("5. 本次抓取无实质性变动，跳过持久化与下发。")
        return

    # 调用新版的历史双表写入方法
    try:
        weibo_mysql_client.save_incremental_data(unique_items)
        logger.info(f"5. 已将 {len(unique_items)} 条增量记录精准写入 MySQL (基础表 + 趋势流水表)")
    except Exception as e:
        logger.error(f"5. MySQL 历史双写流程出错: {e}")

        # 6. 推送至 Kafka 供下游系统 (Flink 等) 计算或消费
        try:
            for item in unique_items:
                # 直接把完整的标准化字典发出去，坚决不删减任何字段！
                # 保障全系统、全链路的 JSON Schema (数据契约) 绝对一致
                kafka_producer.send(
                    topic=KAFKA_CONFIG['topics']['weibo'],
                    message=item.to_dict(),
                    key=item.title  # 依然保留 title 作为精准路由的 Key
                )
            logger.info(f"6. 成功将 {len(unique_items)} 条完整增量数据推送到 Kafka")
        except Exception as e:
            logger.error(f"6. 增量 Kafka 下发流程出错: {e}")

if __name__ == "__main__":
    try:
        while True:
            hotSearchCrawler()
            sleep(CRAWLER_CONFIG['gap_time'])  # 默认每分钟执行一次
    finally:
        # 保证程序被手动强杀 (Ctrl+C) 时优雅关闭数据库连接
        weibo_mysql_client.close()