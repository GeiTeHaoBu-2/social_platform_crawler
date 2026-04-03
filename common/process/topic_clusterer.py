"""
模块名称: topic_clusterer.py
模块职责: 话题聚类器，负责生成话题名称
输入接口: generate_topic_name(keyword: str, title: str, type_name: str) -> str
输出格式: 话题名称字符串，如"刘畊宏健身热潮"
依赖模块: 无（纯算法模块）
作者备注: 
    - 被nlp_pipeline.py调用，不独立对外暴露
    - 基于关键词相似度算法（模拟实现）
"""

from typing import List, Dict


class TopicClusterer:
    """
    话题聚类器
    
    职责:
    基于关键词生成话题名称，相同关键词归为同一话题
    
    实现思路（模拟）:
    1. 提取中心关键词（如"刘畊宏"、"疫情"）
    2. 相同关键词归为同一话题
    3. 生成话题名称：keyword + "热潮"/"事件"/"话题"
    """
    
    # 话题后缀映射（根据分类选择不同后缀）
    TOPIC_SUFFIXES = {
        '娱乐': ['热潮', '话题', '风波', '官宣'],
        '社会': ['事件', '关注', '热议', '话题'],
        '科技': ['发布', '突破', '创新', '热潮'],
        '体育': ['夺冠', '比赛', '热潮', '关注'],
        '财经': ['行情', '动态', '关注', '分析'],
        '未知': ['话题', '关注', '热议']
    }
    
    def __init__(self):
        """初始化话题聚类器"""
        # 简单的话题缓存，用于同一批次内的去重
        self._topic_cache = {}
    
    def _select_suffix(self, title: str, type_name: str) -> str:
        """
        根据标题内容和分类选择合适的话题后缀
        
        Args:
            title: 热搜标题
            type_name: 分类名称
            
        Returns:
            话题后缀字符串
        """
        suffixes = self.TOPIC_SUFFIXES.get(type_name, self.TOPIC_SUFFIXES['未知'])
        
        # 根据标题内容选择最合适的后缀
        if '直播' in title or '火爆' in title or '热' in title:
            return '热潮'
        elif '结婚' in title or '离婚' in title or '宣布' in title:
            return '官宣'
        elif '夺冠' in title or '冠军' in title or '胜利' in title:
            return '夺冠'
        elif '发布' in title or '新品' in title or '上市' in title:
            return '发布'
        elif '事故' in title or '灾难' in title or '危机' in title:
            return '事件'
        else:
            # 默认选择第一个
            return suffixes[0]
    
    def generate_topic_name(self, keyword: str, title: str, type_name: str) -> str:
        """
        生成话题名称
        
        Args:
            keyword: 核心关键词，如"刘畊宏"
            title: 完整标题，如"刘畊宏直播健身火爆全网"
            type_name: 分类名称，如"娱乐"
        
        Returns:
            str: 话题名称，如"刘畊宏健身热潮"
        
        实现逻辑:
            1. 基于关键词和分类选择后缀
            2. 组合生成话题名称
        """
        if not keyword:
            return '其他话题'
        
        # 选择后缀
        suffix = self._select_suffix(title, type_name)
        
        # 生成话题名称
        topic_name = f"{keyword}{suffix}"
        
        return topic_name
    
    def cluster_batch(self, items: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """
        批量话题聚类（保留用于未来扩展）
        
        Args:
            items: 热搜列表，每个元素包含keyword和title
                   如 [{"keyword": "刘畊宏", "title": "xxx", "type_name": "娱乐"}, ...]
        
        Returns:
            dict: {keyword: {"topic_name": str, "count": int}}
        """
        topic_groups = {}
        
        for item in items:
            keyword = item.get('keyword', '')
            title = item.get('title', '')
            type_name = item.get('type_name', '未知')
            
            if keyword not in topic_groups:
                topic_groups[keyword] = {
                    'topic_name': self.generate_topic_name(keyword, title, type_name),
                    'count': 0,
                    'type_name': type_name
                }
            
            topic_groups[keyword]['count'] += 1
        
        return topic_groups


if __name__ == '__main__':
    # 测试代码
    clusterer = TopicClusterer()
    
    test_cases = [
        {'keyword': '刘畊宏', 'title': '刘畊宏直播健身火爆全网', 'type_name': '娱乐'},
        {'keyword': '某明星', 'title': '某明星宣布结婚喜讯', 'type_name': '娱乐'},
        {'keyword': '股市', 'title': '股市大跌引发关注', 'type_name': '财经'},
        {'keyword': 'AI', 'title': 'AI技术突破改变生活', 'type_name': '科技'},
        {'keyword': '国足', 'title': '国足夺冠创造历史', 'type_name': '体育'},
    ]
    
    print("=== 单条话题生成测试 ===")
    for case in test_cases:
        topic = clusterer.generate_topic_name(
            case['keyword'], 
            case['title'], 
            case['type_name']
        )
        print(f"关键词: {case['keyword']}, 分类: {case['type_name']} -> 话题: {topic}")
    
    print("\n=== 批量聚类测试 ===")
    batch_result = clusterer.cluster_batch(test_cases)
    for keyword, info in batch_result.items():
        print(f"关键词: {keyword}, 话题: {info['topic_name']}, 数量: {info['count']}")
