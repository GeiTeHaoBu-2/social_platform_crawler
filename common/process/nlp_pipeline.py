"""
模块名称: nlp_pipeline.py
模块职责: 自然语言处理流水线，负责情感分析、分类、话题生成，以及NLP缓存筛查
输入接口: analyze(title: str) -> dict, process_items(items: list) -> list
输出格式: {"sentiment_score": float, "type_name": str, "topic_name": str}
依赖模块: common.storage.redis_client(用于缓存), common.process.topic_clusterer(话题聚类)
作者备注: 
    - 合并原deduplicationer.py逻辑：基于Redis缓存判断是否需要NLP分析
    - 缓存仅用于避免重复NLP计算，不影响Kafka消息发送
    - 所有物品无论缓存是否命中，都必须发送Kafka
"""

import json
import hashlib
import time
from typing import List, Dict, Any, Optional
import redis

from common.process.topic_clusterer import TopicClusterer
from common.utils.logging_config import logger


class NLPPipeline:
    """
    NLP处理流水线
    
    职责:
    1. 对热搜标题进行情感分析、分类、话题生成
    2. 使用Redis缓存避免重复NLP计算
    3. 缓存仅用于优化NLP，不影响Kafka消息发送
    
    缓存策略:
    - Key: nlp_cache:{item_id} (item_id为title的MD5)
    - Value: {"sentiment_score": 0.5, "type_name": "娱乐", "topic_name": "xxx"}
    - TTL: 86400秒（24小时）
    """
    
    # Redis缓存TTL（秒）
    CACHE_TTL = 86400  # 24小时
    
    # 情感词典（简单规则实现）
    POSITIVE_WORDS = ['恭喜', '成功', '胜利', '突破', '冠军', '热门', '火爆', '赞', '好', '喜', '乐', '幸福']
    NEGATIVE_WORDS = ['悲剧', '灾难', '死亡', '事故', '失败', '危机', '暴', '恶', '惨', '痛', '哭', '骂']
    
    # 分类关键词映射
    TYPE_KEYWORDS = {
        '娱乐': ['明星', '演员', '歌手', '电影', '电视剧', '综艺', '演唱会', '红毯', '颁奖', '恋爱', '结婚', '离婚', '出轨'],
        '社会': ['疫情', '事故', '灾难', '法律', '政策', '民生', '教育', '医疗', '就业', '房价'],
        '科技': ['手机', '电脑', 'AI', '人工智能', '芯片', '发布会', '华为', '苹果', '小米', '科技'],
        '体育': ['足球', '篮球', 'NBA', '世界杯', '奥运', '冠军', '比赛', '运动员', '球队', '夺冠'],
        '财经': ['股市', '基金', '房价', '经济', 'GDP', '通胀', '利率', '银行', '投资', '理财'],
    }
    
    def __init__(self, redis_config: Optional[Dict[str, Any]] = None):
        """
        初始化NLP流水线
        
        Args:
            redis_config: Redis配置字典，如果为None则使用默认配置
        """
        # 初始化Redis连接
        if redis_config is None:
            from common.config.settings import REDIS_CONFIG
            redis_config = REDIS_CONFIG
        
        try:
            self.redis_client = redis.Redis(
                host=redis_config.get('host', '127.0.0.1'),
                port=redis_config.get('port', 6379),
                db=redis_config.get('data_db', 0),  # 使用data_db存储NLP缓存
                password=redis_config.get('password', None),
                decode_responses=True
            )
            logger.info("NLP Pipeline Redis连接成功")
        except Exception as e:
            logger.error(f"NLP Pipeline Redis连接失败: {e}")
            self.redis_client = None
        
        # 初始化话题聚类器
        self.topic_clusterer = TopicClusterer()
    
    def _generate_item_id(self, title: str) -> str:
        """基于title生成item_id"""
        return hashlib.md5(title.encode('utf-8')).hexdigest()
    
    def _get_cache_key(self, item_id: str) -> str:
        """生成缓存key"""
        return f"nlp_cache:{item_id}"
    
    def _check_cache(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        检查NLP缓存
        
        Args:
            item_id: 物品ID
            
        Returns:
            缓存结果或None
        """
        if not self.redis_client:
            return None
        
        try:
            cache_key = self._get_cache_key(item_id)
            cached = self.redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.error(f"读取NLP缓存失败: {e}")
        
        return None
    
    def _write_cache(self, item_id: str, result: Dict[str, Any]):
        """
        写入NLP缓存
        
        Args:
            item_id: 物品ID
            result: NLP分析结果
        """
        if not self.redis_client:
            return
        
        try:
            cache_key = self._get_cache_key(item_id)
            self.redis_client.setex(
                cache_key,
                self.CACHE_TTL,
                json.dumps(result, ensure_ascii=False)
            )
        except Exception as e:
            logger.error(f"写入NLP缓存失败: {e}")
    
    def _extract_keyword(self, title: str) -> str:
        """
        从标题中提取核心关键词
        
        实现思路:
        1. 优先提取人名（2-4个连续中文字符）
        2. 如果没有明显人名，提取前4个字符作为关键词
        """
        import re
        
        # 尝试匹配可能的人名（简单规则：2-4个中文字符）
        # 实际项目中可使用jieba分词或NER模型
        patterns = [
            r'([\u4e00-\u9fa5]{2,4})(?=直播|健身|演唱|电影|剧|夺冠)',  # 刘畊宏直播 -> 刘畊宏
            r'([\u4e00-\u9fa5]{2,4})(?=.{0,2}[获得|宣布|表示])',       # 人名+动词
        ]
        
        for pattern in patterns:
            match = re.search(pattern, title)
            if match:
                return match.group(1)
        
        # 默认取前4个字符
        return title[:4] if len(title) >= 4 else title
    
    def _calc_sentiment(self, title: str) -> float:
        """
        计算情感分数
        
        返回: -1(负面) 到 1(正面) 之间的浮点数
        
        实现逻辑:
        1. 统计正面词和负面词的出现次数
        2. 根据词频计算情感倾向
        """
        positive_count = sum(1 for word in self.POSITIVE_WORDS if word in title)
        negative_count = sum(1 for word in self.NEGATIVE_WORDS if word in title)
        
        if positive_count == 0 and negative_count == 0:
            return 0.0  # 中性
        
        # 计算情感分数 (-1 到 1)
        total = positive_count + negative_count
        score = (positive_count - negative_count) / max(total, 1)
        
        # 归一化到 -1 ~ 1
        return max(-1.0, min(1.0, score))
    
    def _classify_type(self, title: str) -> str:
        """
        对标题进行分类
        
        返回: 娱乐/社会/科技/体育/财经/未知
        """
        for type_name, keywords in self.TYPE_KEYWORDS.items():
            if any(keyword in title for keyword in keywords):
                return type_name
        
        return '未知'
    
    def analyze(self, title: str) -> Dict[str, Any]:
        """
        对热搜标题进行NLP分析
        
        Args:
            title: 热搜标题文本，如"刘畊宏直播健身火爆全网"
        
        Returns:
            dict: 包含三个字段的分析结果
                - sentiment_score: 情感分数，范围-1(负面)到1(正面)
                - type_name: 内容分类，如"娱乐"、"社会"、"科技"
                - topic_name: 话题名称，如"刘畊宏健身热潮"
        
        实现逻辑:
            1. 提取关键词（如"刘畊宏"）
            2. 基于关键词词典判断情感倾向
            3. 基于规则生成分类和话题名
        """
        # Step 1: 提取核心关键词
        keyword = self._extract_keyword(title)
        logger.info(f"提取关键词: '{keyword}' 从标题: '{title}'")
        
        # Step 2: 查询情感词典判断正负面
        sentiment_score = self._calc_sentiment(title)
        logger.info(f"计算情感分数: {sentiment_score} 对标题: '{title}'")
        
        # Step 3: 基于规则生成分类
        type_name = self._classify_type(title)
        logger.info(f"分类结果: '{type_name}' 对标题: '{title}'")
        
        # Step 4: 生成话题名称
        topic_name = self.topic_clusterer.generate_topic_name(keyword, title, type_name)
        logger.info(f"生成话题名称: '{topic_name}' 对标题: '{title}'")
        
        return {
            'sentiment_score': round(sentiment_score, 2),
            'type_name': type_name,
            'topic_name': topic_name
        }
    
    def process_items(self, items: List) -> List[Dict[str, Any]]:
        """
        批量处理热搜条目，带缓存筛查
        
        处理流程:
        1. 对每个item，先查缓存
        2. 缓存命中：直接使用缓存结果
        3. 缓存未命中：调用NLP分析，写入缓存
        4. 所有item都必须返回完整数据（用于Kafka发送）
        
        Args:
            items: HotSearchItem对象列表
            
        Returns:
            List[Dict]: 包含完整信息的字典列表，每个字典包含:
                - item_id, title, rank, heat, crawl_time
                - sentiment_score, type_name, topic_name
                - is_from_cache: 是否来自缓存（用于调试）
        """
        results = []
        logger.info(f"开始处理 {len(items)} 条热搜条目，进行NLP分析和缓存筛查")
        
        for item in items:
            try:
                item_id = self._generate_item_id(item.title)
                
                # Step 1: 检查缓存
                cached_result = self._check_cache(item_id)
                logger.debug(f"检查NLP缓存: item_id={item_id}, title='{item.title}', 缓存结果: {cached_result}")
                
                if cached_result:
                    # 缓存命中：直接使用
                    nlp_result = cached_result
                    is_from_cache = True
                    logger.debug(f"NLP缓存命中: {item.title}")
                else:
                    # 缓存未命中：调用NLP分析
                    nlp_result = self.analyze(item.title)
                    # 写入缓存
                    self._write_cache(item_id, nlp_result)
                    is_from_cache = False
                    logger.debug(f"NLP分析完成: {item.title}")
                
                # Step 2: 组装完整结果（所有字段必须非空）
                full_result = {
                    'item_id': item_id,
                    'title': item.title,
                    'rank_pos': item.rank,
                    'heat': item.heat,
                    'crawl_time': item.latest_crawl_time,
                    'sentiment_score': nlp_result.get('sentiment_score', 0.0),
                    'type_name': nlp_result.get('type_name', '未知'),
                    'topic_name': nlp_result.get('topic_name', '其他话题'),
                    'source': 'weibo',
                    'is_from_cache': is_from_cache  # 调试用，发送Kafka前可删除
                }
                
                # Step 3: 确保所有字段都不为null（Kafka契约要求）
                if full_result['sentiment_score'] is None:
                    full_result['sentiment_score'] = 0.0
                if not full_result['type_name']:
                    full_result['type_name'] = '未知'
                if not full_result['topic_name']:
                    full_result['topic_name'] = '其他话题'
                
                results.append(full_result)
                
            except Exception as e:
                logger.error(f"NLP处理失败 [{item.title}]: {e}")
                # 异常时返回默认值，确保不影响其他数据
                results.append({
                    'item_id': self._generate_item_id(item.title),
                    'title': item.title,
                    'rank_pos': item.rank,
                    'heat': item.heat,
                    'crawl_time': item.latest_crawl_time,
                    'sentiment_score': 0.0,
                    'type_name': '未知',
                    'topic_name': '其他话题',
                    'source': 'weibo',
                    'is_from_cache': False
                })
        
        return results
    
    def get_items_for_db_write(self, processed_items: List[Dict[str, Any]]) -> tuple:
        """
        从处理后的items中分离出需要写入数据库的items
        
        由于缓存命中时也需要写Kafka但不需要重复写DB，
        此方法返回需要写入DB的base_items和analysis_items
        
        Args:
            processed_items: process_items返回的结果
            
        Returns:
            tuple: (base_items, analysis_items)
                - base_items: HotSearchItem列表（用于写weibo_base）
                - analysis_items: 字典列表（用于写weibo_analysis）
        """
        from common.models.item import HotSearchItem
        
        base_items = []
        analysis_items = []
        
        for item in processed_items:
            # 所有item都需要写base表（INSERT IGNORE保护first_time）
            base_item = HotSearchItem(
                rank=item['rank_pos'],
                title=item['title'],
                url='',  # 在main中补充
                heat=item['heat'],
                latest_crawl_time=item['crawl_time']
            )
            base_items.append(base_item)
            
            # 所有item都需要写analysis表（缓存未命中的才需要，但批量写入没问题）
            analysis_item = {
                'item_id': item['item_id'],
                'sentiment_score': item['sentiment_score'],
                'type_name': item['type_name'],
                'topic_name': item['topic_name'],
                'nlp_time': int(time.time())
            }
            analysis_items.append(analysis_item)
        
        return base_items, analysis_items


if __name__ == '__main__':
    # 测试代码
    pipeline = NLPPipeline()
    
    test_titles = [
        "刘畊宏直播健身火爆全网",
        "某明星宣布结婚喜讯",
        "股市大跌引发关注",
        "科技突破改变生活"
    ]
    
    from common.models.item import HotSearchItem
    
    test_items = [
        HotSearchItem(
            rank=i+1,
            title=title,
            url=f"https://weibo.com/test{i}",
            heat=1000000,
            latest_crawl_time=int(time.time())
        )
        for i, title in enumerate(test_titles)
    ]
    
    results = pipeline.process_items(test_items)
    for r in results:
        print(f"标题: {r['title']}")
        print(f"  情感分: {r['sentiment_score']}, 分类: {r['type_name']}, 话题: {r['topic_name']}")
        print(f"  来自缓存: {r['is_from_cache']}")
        print()
