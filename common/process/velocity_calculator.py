"""
模块名称: velocity_calculator.py
模块职责: 热搜加速度计算器
"""
from typing import List, Dict, Tuple, Optional
from common.models.item import HotSearchItem
from common.storage.redis_manager import RedisManager
from common.utils.logging_config import logger


class VelocityCalculator:
    def __init__(self, redis_manager: RedisManager):
        self.redis = redis_manager
    
    def calculate(self, current_items: List[HotSearchItem], 
                  current_time: int, 
                  platform: str = 'weibo') -> Dict[str, Tuple[float, float]]:
        """
        计算加速度
        
        Args:
            current_items: 当前热搜列表
            current_time: 当前时间戳（秒）
            platform: 平台标识
            
        Returns:
            {item_id: (heat_velocity, rank_velocity)}
        """
        result = {}
        
        last_data = self.redis.get_last_hot_search(platform)
        if not last_data:
            logger.info("无上一轮数据，所有加速度设为0")
            for item in current_items:
                result[item.item_id] = (0.0, 0.0)
            return result
        
        logger.info(f"读取到上一轮数据: {len(last_data)} 条")
        
        last_index = {}
        for item in last_data:
            item_id = item.get('item_id')
            if item_id:
                last_index[item_id] = {
                    'heat': item.get('heat', 0),
                    'rank': item.get('rank', 0),
                    'crawl_time': item.get('latest_crawl_time', 0)
                }
        
        matched_count = 0
        for item in current_items:
            if item.item_id in last_index:
                last = last_index[item.item_id]
                time_diff = (current_time - last['crawl_time']) / 60.0
                
                if time_diff > 0:
                    heat_velocity = (item.heat - last['heat']) / time_diff
                    rank_velocity = (item.rank - last['rank']) / time_diff
                    matched_count += 1
                    logger.debug(f"加速度计算: {item.title[:20]} | heat_vel={heat_velocity:.2f}, rank_vel={rank_velocity:.2f}, time_diff={time_diff:.2f}min")
                else:
                    heat_velocity = 0.0
                    rank_velocity = 0.0
                    logger.debug(f"时间差为0: {item.title[:20]}")
            else:
                heat_velocity = 0.0
                rank_velocity = 0.0
            
            result[item.item_id] = (heat_velocity, rank_velocity)
        
        logger.info(f"加速度计算完成: 匹配到历史数据 {matched_count}/{len(current_items)} 条")
        
        return result
