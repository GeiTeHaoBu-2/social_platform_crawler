"""简单脚本：用于测试 Kafka Producer 是否能发送消息到指定 topic。"""
import time
import logging
from common.transmit.kafka_producer import send_hot_search

logging.basicConfig(level=logging.INFO)

if __name__ == '__main__':
    sample = {
        'title': '示例热搜测试',
        'rank': 1,
        'hot_count': '1万',
        'tag': '热',
        'url': 'https://s.weibo.com/example',
        'first_crawled': int(time.time()),
        'source': 'weibo'
    }
    try:
        print("xxxxxxxxxxxxxx0")

        send_hot_search(sample)
        print('✅ Sent sample message to Kafka (if configured).')
    except Exception as e:
        print('❌ Sending sample failed:', e)
