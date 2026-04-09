import sys
sys.path.insert(0, '.')

from common.storage.mysql_client import MySQLClient
from common.models.item import HotSearchItem
from datetime import datetime

config = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'social_platforms_analysis',
    'charset': 'utf8mb4'
}

print('测试MySQL连接...')
client = MySQLClient(config=config, platform='weibo')

test_item = HotSearchItem(
    rank=1,
    title='测试热搜1' + str(int(datetime.now().timestamp())),
    url='https://weibo.com/test',
    heat=5000000,
    latest_crawl_time=int(datetime.now().timestamp()),
    first_on_board_time=int(datetime.now().timestamp())
)

print('测试写入base表...')
count = client.batch_write_base([test_item])
print(f'写入base表: {count} 条')

test_analysis = [{
    'item_id': client._generate_item_id(test_item.title),
    'sentiment_score': 0.5,
    'type_name': '娱乐',
    'topic_name': '测试话题',
    'nlp_time': int(datetime.now().timestamp())
}]
print('测试写入analysis表...')
count = client.batch_write_analysis(test_analysis)
print(f'写入analysis表: {count} 条')

client.close()
print('测试完成!')
