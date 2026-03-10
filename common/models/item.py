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
        # 说明这是一个刚刚被爬虫发现的“全新话题”，它的初次上榜时间就是当前的爬取时间。
        self.first_on_board_time = first_on_board_time if first_on_board_time is not None else latest_crawl_time

    def to_dict(self):
        """
        转换为字典格式，方便存入 Redis 或 MySQL。

        【架构备忘】：
        1. 这里的 url 必须被完整保留并序列化，因为前端大屏(Redis)和历史底座(MySQL base表)强依赖它。
        2. 若为了节省网络带宽，请在推入 Kafka 之前，在调用方(如 main.py)手动从生成的字典中剔除 'url' 字段。
        3. 坚决保留值为 None 的字段（映射为 JSON 的 null），保证对外数据契约(Schema)的绝对严谨统一。
        :return: 字典格式的热搜条目
        """
        return {
            'rank': self.rank,
            'title': self.title,
            'url': self.url,
            'heat': self.heat,
            'latest_crawl_time': self.latest_crawl_time,
            'first_on_board_time': self.first_on_board_time
        }