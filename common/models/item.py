from typing import Optional
import hashlib


class HotSearchItem:
    def __init__(self, rank: int, title: str, url: str, heat: int, latest_crawl_time: int,
                 first_on_board_time: Optional[int] = None):
        self.rank = rank
        self.title = title
        self.url = url
        self.heat = heat
        self.latest_crawl_time = latest_crawl_time
        self.first_on_board_time = first_on_board_time if first_on_board_time is not None else latest_crawl_time
        self._item_id: Optional[str] = None

    @property
    def item_id(self) -> str:
        if self._item_id is None:
            self._item_id = hashlib.md5(self.title.encode('utf-8')).hexdigest()
        return self._item_id

    @staticmethod
    def generate_item_id(title: str) -> str:
        return hashlib.md5(title.encode('utf-8')).hexdigest()

    def to_dict(self, include_url: bool = True) -> dict:
        result = {
            'rank': self.rank,
            'title': self.title,
            'heat': self.heat,
            'latest_crawl_time': self.latest_crawl_time,
            'first_on_board_time': self.first_on_board_time,
            'item_id': self.item_id
        }
        
        if include_url:
            result['url'] = self.url
            
        return result
    
    def to_kafka_dict(self, nlp_result: Optional[dict] = None) -> dict:
        result = {
            'item_id': self.item_id,
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
