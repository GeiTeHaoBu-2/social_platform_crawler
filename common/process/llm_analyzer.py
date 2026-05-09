"""
模块名称: llm_analyzer.py
模块职责: 基于大模型的热搜分析器（主入口）

子模块:
- llm_cache.py: 缓存管理
- llm_prompts.py: Prompts加载
- llm_client.py: API客户端
- llm_topic_extractor.py: 话题提取降级方案

使用示例:
    from common.process.llm_analyzer import LLMAnalyzer
    analyzer = LLMAnalyzer(api_config, redis_config)
    result = analyzer.analyze("标题")
    results = analyzer.analyze_batch(["标题1", "标题2"])
"""
import time
from typing import List, Dict, Any, Optional, Tuple

from common.utils.logging_config import logger
from common.process.llm_cache import LLMCache
from common.process.llm_prompts import PromptLoader
from common.process.llm_client import LLMClient
from common.process.llm_topic_extractor import TopicExtractor


class LLMAnalyzer:
    """
    大模型分析器（主类，<400行）
    
    职责:
    1. 对热搜标题进行深度语义分析
    2. 情感分析、类型分类、话题提炼
    3. 批量处理、结果缓存
    """
    
    # 批处理大小
    BATCH_SIZE = 10
    
    def __init__(self, api_config: Optional[Dict[str, Any]] = None,
                 redis_config: Optional[Dict[str, Any]] = None):
        """
        初始化LLM分析器
        
        Args:
            api_config: API配置字典（支持多模型配置）
            redis_config: Redis配置字典
        """
        # 加载配置
        if api_config is None:
            try:
                from common.config.settings import LLM_CONFIG
                api_config = LLM_CONFIG
            except ImportError:
                api_config = {}
        
        # 初始化组件（传入完整配置，包括primary/backup/failover）
        self.client = LLMClient(api_config)
        self.cache = LLMCache(redis_config)
        
        # 加载Prompts
        self.system_prompt, self.batch_system_prompt = PromptLoader.load()
        
        logger.info("🤖 LLM Analyzer初始化完成")
    
    def analyze(self, title: str) -> Dict[str, Any]:
        """
        单条热搜分析（带缓存）
        
        Args:
            title: 热搜标题
            
        Returns:
            分析结果字典
        """
        # 1. 检查缓存
        cached = self.cache.get(title)
        if cached:
            self.cache.record_hit()
            logger.debug(f"LLM缓存命中: {title[:20]}...")
            return cached
        
        self.cache.record_miss()
        
        # 2. 调用API
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请分析以下热搜标题：\n{title}"}
        ]
        
        content = self.client.chat(messages)
        if content:
            result = self.client.parse_json_response(content)
            if result:
                self.cache.set(title, result)
                return result
        
        # 3. 失败时返回默认值
        logger.warning(f"LLM分析失败，使用默认值: {title[:30]}")
        return self._default_result(title)
    
    def analyze_batch(self, titles: List[str]) -> List[Dict[str, Any]]:
        """
        批量热搜分析（带缓存优化）
        
        Args:
            titles: 热搜标题列表
            
        Returns:
            分析结果列表，与输入顺序一致
        """
        if not titles:
            return []
        
        # 1. 分离缓存命中和未命中
        results, titles_to_analyze, cache_map = self._split_by_cache(titles)
        
        # 2. 批量分析未缓存的
        if titles_to_analyze:
            logger.info(f"LLM批量分析: {len(titles_to_analyze)} 条需要API调用，"
                       f"{len(results)} 条来自缓存")
            
            batch_results = self._analyze_in_batches(titles_to_analyze)
            
            # 合并结果并保存到缓存
            for title, result in zip(titles_to_analyze, batch_results):
                idx = cache_map[title]
                results.append((idx, result))
                self.cache.set(title, result)
        
        # 3. 按原始顺序排序
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results]
    
    def process_items(self, items: List[Any], redis_config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        处理HotSearchItem列表（兼容原接口）
        
        Args:
            items: HotSearchItem对象列表
            redis_config: Redis配置（用于缓存，可选）
            
        Returns:
            包含分析结果的字典
        """
        if not items:
            return {'all_results': [], 'new_items': [], 'analysis_results': []}
        
        # 确保Redis已初始化
        if redis_config and not self.cache.redis_client:
            self.cache._init_redis(redis_config)
        
        # 提取标题并分析
        titles = [item.title for item in items]
        analysis_results, new_indices = self._analyze_with_cache_info(titles)
        
        # 组装结果
        all_results = []
        new_items = []
        
        for i, (item, analysis) in enumerate(zip(items, analysis_results)):
            item_id = item.item_id
            
            result = {
                'item_id': item_id,
                'title': item.title,
                'rank_pos': item.rank,
                'heat': item.heat,
                'crawl_time': item.latest_crawl_time,
                'sentiment_score': analysis.get('sentiment_score', 0.0),
                'topic_name': analysis.get('topic_name', ''),
                'type_name': analysis.get('type_name', '其他'),
                'keywords': analysis.get('keywords', []),
                'source': 'weibo'
            }
            all_results.append(result)
            
            if i in new_indices:
                new_items.append(item)
                is_new = "[NEW]"
            else:
                is_new = "[CACHE]"
            
            # 实时输出处理结果
            logger.info(f"[Item处理] {is_new} Rank:{item.rank:2d} | "
                       f"热度:{item.heat:>8} | "
                       f"情感:{analysis.get('sentiment_score', 0):.2f} | "
                       f"类型:{analysis.get('type_name', '其他'):6s} | "
                       f"{item.title[:25]}{'...' if len(item.title) > 25 else ''}")
        
        # 输出缓存统计
        hit_rate = self.cache.get_hit_rate()
        logger.info(f"LLM缓存命中率: {hit_rate:.1f}%, 新数据: {len(new_items)}条")
        
        return {
            'all_results': all_results,
            'new_items': new_items,
            'analysis_results': all_results
        }
    
    def get_items_for_db_write(self, processed_items: List[Dict[str, Any]]) -> tuple:
        """
        从处理后的items中分离出需要写入数据库的items
        
        Args:
            processed_items: process_items返回的analysis_results
            
        Returns:
            tuple: (analysis_items, topic_items)
                - analysis_items: 字典列表（用于写weibo_analysis）
                - topic_items: 空列表（兼容接口，LLM不使用topic聚类表）
        """
        analysis_items = []
        
        for item in processed_items:
            analysis_item = {
                'item_id': item['item_id'],
                'sentiment_score': item['sentiment_score'],
                'type_name': item['type_name'],
                'topic_name': item['topic_name'],
                'llm_time': int(time.time())
            }
            analysis_items.append(analysis_item)
        
        # 返回空列表作为topic_items（兼容接口）
        return analysis_items, []
    
    def get_stats(self) -> Dict[str, Any]:
        """获取分析统计信息"""
        hits, misses = self.cache.get_stats()
        return {
            'cache_hits': hits,
            'cache_misses': misses,
            'hit_rate': self.cache.get_hit_rate()
        }
    
    # ==================== 私有方法 ====================
    
    def _split_by_cache(self, titles: List[str]) -> Tuple[List, List[str], Dict]:
        """将标题列表按缓存状态分离"""
        results = []  # (index, result) 列表
        cache_map = {}  # title -> index
        titles_to_analyze = []
        
        for i, title in enumerate(titles):
            cached = self.cache.get(title)
            if cached:
                self.cache.record_hit()
                results.append((i, cached))
            else:
                self.cache.record_miss()
                cache_map[title] = i
                titles_to_analyze.append(title)
        
        return results, titles_to_analyze, cache_map
    
    def _analyze_in_batches(self, titles: List[str]) -> List[Dict[str, Any]]:
        """分批分析标题"""
        all_results = []
        total_batches = (len(titles) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        
        for i in range(0, len(titles), self.BATCH_SIZE):
            batch_num = i // self.BATCH_SIZE + 1
            batch = titles[i:i + self.BATCH_SIZE]
            logger.info(f"[LLM分析] 批次 {batch_num}/{total_batches}: 分析 {len(batch)} 条标题")
            
            batch_results = self._call_batch_api(batch)
            all_results.extend(batch_results)
            
            # 实时输出每批结果
            for j, (title, result) in enumerate(zip(batch, batch_results)):
                logger.info(f"[LLM结果] [{i+j+1}/{len(titles)}] 标题: {title[:30]}... | "
                          f"情感: {result.get('sentiment_score', 0):.2f} | "
                          f"类型: {result.get('type_name', '未知')} | "
                          f"话题: {result.get('topic_name', '无')[:20]}")
        
        logger.info(f"[LLM分析] 完成: 共 {len(all_results)} 条")
        return all_results
    
    def _call_batch_api(self, titles: List[str]) -> List[Dict[str, Any]]:
        """调用批量分析API"""
        if not titles:
            return []
        
        # 构建输入
        titles_text = "\n".join([f"{i+1}. {title}" for i, title in enumerate(titles)])
        messages = [
            {"role": "system", "content": self.batch_system_prompt},
            {"role": "user", "content": f"请批量分析以下{len(titles)}个热搜标题：\n\n{titles_text}"}
        ]
        
        # 调用API
        content = self.client.chat(messages, temperature=0.2)
        if not content:
            logger.warning(f"LLM批量分析API失败，退化为逐个分析: {len(titles)}条")
            return [self.analyze(t) for t in titles]
        
        # 解析响应
        result = self.client.parse_json_response(content)
        if not result:
            logger.warning(f"LLM批量分析解析失败，退化为逐个分析: {len(titles)}条")
            return [self.analyze(t) for t in titles]
        
        # 确保返回列表格式
        if isinstance(result, list):
            return self._normalize_results(result, titles)
        elif isinstance(result, dict):
            return [result] + [self._default_result(t) for t in titles[1:]]
        else:
            return [self._default_result(t) for t in titles]
    
    def _normalize_results(self, results: List[Dict], titles: List[str]) -> List[Dict[str, Any]]:
        """规范化批量分析结果"""
        # 补充缺失的结果
        while len(results) < len(titles):
            results.append(self._default_result(titles[len(results)]))
        
        return results[:len(titles)]
    
    def _analyze_with_cache_info(self, titles: List[str]) -> Tuple[List[Dict], set]:
        """批量分析并返回新数据索引"""
        results = []
        new_indices = set()
        cache_map = {}
        titles_to_analyze = []
        
        for i, title in enumerate(titles):
            cached = self.cache.get(title)
            if cached:
                self.cache.record_hit()
                results.append((i, cached))
            else:
                self.cache.record_miss()
                new_indices.add(i)
                cache_map[title] = i
                titles_to_analyze.append(title)
        
        # 分析未缓存的
        if titles_to_analyze:
            logger.info(f"[LLM分析] 缓存未命中: {len(titles_to_analyze)} 条需要调用API")
            batch_results = self._analyze_in_batches(titles_to_analyze)
            for title, result in zip(titles_to_analyze, batch_results):
                idx = cache_map[title]
                results.append((idx, result))
                self.cache.set(title, result)
        else:
            logger.info("[LLM分析] 全部命中缓存，无需调用API")
        
        results.sort(key=lambda x: x[0])
        return [r[1] for r in results], new_indices
    
    def _default_result(self, title: str) -> Dict[str, Any]:
        """生成默认分析结果"""
        return {
            'sentiment_score': 0.0,
            'type_name': '其他',
            'topic_name': TopicExtractor.extract(title),
            'keywords': []
        }
    
# 向后兼容：保留原有导入
__all__ = ['LLMAnalyzer']
