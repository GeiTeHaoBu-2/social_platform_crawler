"""
模块名称: llm_topic_extractor.py
模块职责: 话题提取器，用于LLM失败时的降级处理
"""
import re


class TopicExtractor:
    """话题提取器（LLM失败时的降级方案）"""
    
    # 常见后缀词，用于清洗标题
    SUFFIXES = [
        '直播', '引发', '导致', '造成', '登上', '热搜', '网友', '评论',
        '曝光', '回应', '宣布', '确认', '否认', '今日', '明日', '大涨',
        '大跌', '突破', '关注', '热议', '讨论', '称', '说', '表示',
        '最新消息', '详情', '来了', '曝光', '视频', '图片'
    ]
    
    @classmethod
    def extract(cls, title: str, max_length: int = 6) -> str:
        """
        从标题中提取核心话题
        
        Args:
            title: 热搜标题
            max_length: 最大长度限制
            
        Returns:
            提取的核心话题
        """
        if not title:
            return "未知"
        
        # 移除常见后缀
        clean_title = title
        for suffix in cls.SUFFIXES:
            if clean_title.endswith(suffix) and len(clean_title) > len(suffix):
                clean_title = clean_title[:-len(suffix)]
                break
        
        # 匹配开头的实体（可能是人名、地名、事件名）
        # 尝试匹配前2-6个汉字
        match = re.match(r'^[\u4e00-\u9fa5]{2,' + str(max_length) + '}', clean_title)
        if match:
            return match.group(0)
        
        # 如果没匹配到，返回前max_length个字
        return clean_title[:max_length] if len(clean_title) > max_length else clean_title
    
    @classmethod
    def extract_keywords(cls, title: str, max_keywords: int = 5) -> list[str]:
        """
        从标题中提取关键词
        
        Args:
            title: 热搜标题
            max_keywords: 最大关键词数量
            
        Returns:
            关键词列表
        """
        if not title:
            return []
        
        # 简单的关键词提取：按标点分割，过滤短词
        import jieba
        
        words = list(jieba.cut(title))
        keywords = []
        
        # 过滤停用词和短词
        stop_words = {'的', '了', '在', '是', '和', '与', '或', '有', '被', '把', '给', '让'}
        
        for word in words:
            if len(word) >= 2 and word not in stop_words:
                keywords.append(word)
        
        return keywords[:max_keywords]
