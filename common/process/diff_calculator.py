"""
模块名称: diff_calculator.py
模块职责: 热搜差值计算器（热度/排名变化差值）
"""
from typing import List, Dict, Tuple
from common.models.item import HotSearchItem
from common.storage.redis_manager import RedisManager
from common.utils.logging_config import logger


class DiffCalculator:
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
    
    def calculate(self, current_items: List[HotSearchItem], 
                  current_time: int, 
                  platform: str = 'weibo') -> Dict[str, Tuple[int, int]]:
        """
        计算热度/排名差值
        
        Args:
            current_items: 当前热搜列表
            current_time: 当前时间戳（秒），保留参数用于日志
            platform: 平台标识
            
        Returns:
            {item_id: (heat_diff, rank_diff)}
            - heat_diff: 热度差值（正数=上升，负数=下降）
            - rank_diff: 排名差值（负数=上升，正数=下降）
        """
        result = {}
        
        last_data = self.redis.get_last_hot_search(platform)
        if not last_data:
            logger.info("无上一轮数据，所有差值设为0")
            for item in current_items:
                result[item.item_id] = (0, 0)
            return result
        
        logger.info(f"读取到上一轮数据: {len(last_data)} 条")
        
        last_index = {}
        for item in last_data:
            item_id = item.get('item_id')
            if item_id:
                last_index[item_id] = {
                    'heat': item.get('heat', 0),
                    'rank': item.get('rank', 0),
                    'heat_diff': item.get('heat_diff', 0),
                    'rank_diff': item.get('rank_diff', 0)
                }
        
        matched_count = 0
        for item in current_items:
            if item.item_id in last_index:
                last = last_index[item.item_id]
                
                # 热度没变化时保持上次差值
                if item.heat == last['heat']:
                    heat_diff = last['heat_diff']
                else:
                    heat_diff = item.heat - last['heat']
                
                # 排名没变化时保持上次差值
                if item.rank == last['rank']:
                    rank_diff = last['rank_diff']
                else:
                    rank_diff = item.rank - last['rank']
                
                matched_count += 1
                logger.debug(f"差值计算: {item.title[:20]} | heat_diff={heat_diff}, rank_diff={rank_diff}")
            else:
                heat_diff = 0
                rank_diff = 0
            
            result[item.item_id] = (heat_diff, rank_diff)
        
        logger.info(f"差值计算完成: 匹配到历史数据 {matched_count}/{len(current_items)} 条")
        
        return result
