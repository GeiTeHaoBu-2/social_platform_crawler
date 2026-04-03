#定义热搜条目的标准数据结构
from typing import Optional


class HotSearchItem:
    def __init__(self, rank: int, title: str, url: str, heat: int, latest_crawl_time: int,
                 first_on_board_time: Optional[int] = None):
        """
        初始化热搜条目。
        :param rank: 热搜排名
        :param title: 热搜标题
        :param url: 热搜链接
        :param heat: 热度值
        :param latest_crawl_time: 最新爬取时间戳 (绝对会有)
        :param first_on_board_time: 初次上榜时间戳 (非必填，若无则默认等于最新爬取时间)
        """
        self.rank = rank
        self.title = title
        self.url = url
        self.heat = heat
        self.latest_crawl_time = latest_crawl_time

        # 核心逻辑：如果在 Python 初始化这个对象时没有传入初次上榜时间
        # 说明这是一个刚刚被爬虫发现的"全新话题"，它的初次上榜时间就是当前的爬取时间。
        self.first_on_board_time = first_on_board_time if first_on_board_time is not None else latest_crawl_time

    def to_dict(self, include_url: bool = True) -> dict:
        """
        转换为字典格式，方便存入 Redis 或 MySQL。

        【架构备忘】：
        1. 这里的 url 必须被完整保留并序列化，因为前端大屏(Redis)和历史底座(MySQL base表)强依赖它。
        2. 若为了节省网络带宽，请在推入 Kafka 之前，在调用方(如 main.py)手动从生成的字典中剔除 'url' 字段。
        3. 坚决保留值为 None 的字段（映射为 JSON 的 null），保证对外数据契约(Schema)的绝对严谨统一。
        
        Args:
            include_url: 是否包含url字段，Kafka发送时可设为False节省带宽
            
        :return: 字典格式的热搜条目
        """
        result = {
            'rank': self.rank,
            'title': self.title,
            'heat': self.heat,
            'latest_crawl_time': self.latest_crawl_time,
            'first_on_board_time': self.first_on_board_time
        }
        
        if include_url:
            result['url'] = self.url
            
        return result
    
    def to_kafka_dict(self, nlp_result: dict = None) -> dict:
        """
        转换为Kafka消息格式
        
        Args:
            nlp_result: NLP分析结果，包含sentiment_score, type_name, topic_name
            
        Returns:
            dict: 符合Kafka消息契约的字典
        """
        import hashlib
        
        item_id = hashlib.md5(self.title.encode('utf-8')).hexdigest()
        
        result = {
            'item_id': item_id,
            'title': self.title,
            'rank_pos': self.rank,
            'heat': self.heat,
            'crawl_time': self.latest_crawl_time,
            'source': 'weibo'
        }
        
        if nlp_result:
            result['sentiment_score'] = nlp_result.get('sentiment_score', 0.0)
            result['type_name'] = nlp_result.get('type_name', '未知')
            result['topic_name'] = nlp_result.get('topic_name', '其他话题')
        else:
            result['sentiment_score'] = 0.0
            result['type_name'] = '未知'
            result['topic_name'] = '其他话题'
            
        return result
