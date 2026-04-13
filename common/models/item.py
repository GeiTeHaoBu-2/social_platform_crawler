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
        self.heat_velocity: float = 0.0
        self.rank_velocity: float = 0.0
        self.sentiment_score: Optional[float] = None
        self.type_name: Optional[str] = None
        self.topic_name: Optional[str] = None

    @property
    def item_id(self) -> str:
        if self._item_id is None:
            self._item_id = hashlib.md5(self.title.encode('utf-8')).hexdigest()
        return self._item_id

    @staticmethod
    def generate_item_id(title: str) -> str:
        return hashlib.md5(title.encode('utf-8')).hexdigest()

    def to_dict(self, include_url: bool = True, include_nlp: bool = False) -> dict:
        result = {
            'rank': self.rank,
            'title': self.title,
            'heat': self.heat,
            'latest_crawl_time': self.latest_crawl_time,
            'first_on_board_time': self.first_on_board_time,
            'item_id': self.item_id,
            'heat_velocity': self.heat_velocity,
            'rank_velocity': self.rank_velocity
        }
        
        if include_url:
            result['url'] = self.url
        
        if include_nlp:
            result['sentiment_score'] = self.sentiment_score if hasattr(self, 'sentiment_score') else None
            result['type_name'] = self.type_name if hasattr(self, 'type_name') else None
            result['topic_name'] = self.topic_name if hasattr(self, 'topic_name') else None
            
        return result
    
    def to_kafka_dict(self, nlp_result: Optional[dict] = None) -> dict:
        result = {
            'itemId': self.item_id,
            'rankPos': self.rank,
            'title': self.title,
            'url': self.url,
            'heat': self.heat,
            'heatVelocity': self.heat_velocity,
            'rankVelocity': self.rank_velocity,
            'crawlTime': self.latest_crawl_time * 1000
        }
        
        if nlp_result:
            result['sentimentScore'] = nlp_result.get('sentiment_score', 0.0)
            result['typeName'] = nlp_result.get('type_name', '未知')
            result['topicName'] = nlp_result.get('topic_name', '其他话题')
        else:
            result['sentimentScore'] = 0.0
            result['typeName'] = '未知'
            result['topicName'] = '其他话题'
            
        return result
