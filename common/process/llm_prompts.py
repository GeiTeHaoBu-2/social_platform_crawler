"""
模块名称: llm_prompts.py
模块职责: LLM Prompts 加载和管理
"""
import os
import re
from typing import Optional, Tuple
from common.utils.logging_config import logger


class PromptLoader:
    """LLM Prompts 加载器"""
    
    # Prompts文件路径
    PROMPTS_FILE = "docs/llm_prompts.md"
    
    # 默认Prompts（当文件加载失败时使用）
    DEFAULT_SYSTEM_PROMPT = """你是一个专业的新闻舆情分析专家。你的任务是对微博热搜标题进行深度语义分析。

你需要为每个热搜标题提供以下分析：
1. sentiment_score: -1.0到1.0之间的情感分数
2. type_name: 类别（娱乐/社会/科技/体育/财经/时政/健康/教育/其他）
3. topic_name: 提炼的话题名称（10字以内）
4. keywords: 2-5个核心关键词列表

输出格式必须是严格的JSON，格式如下：
{
    "sentiment_score": 0.75,
    "type_name": "娱乐",
    "topic_name": "刘畊宏健身热潮",
    "keywords": ["刘畊宏", "健身", "直播"]
}
注意：只输出JSON，不要有任何其他文字。"""

    DEFAULT_BATCH_SYSTEM_PROMPT = """你是一个专业的新闻舆情分析专家。对多个微博热搜标题进行批量深度语义分析。

为每个热搜提供分析：
1. sentiment_score: -1.0到1.0的情感分数
2. type_name: 类别（娱乐/社会/科技/体育/财经/时政/健康/教育/其他）
3. topic_name: 提炼的话题名称（10字以内）
4. keywords: 2-5个核心关键词列表

输出格式必须是严格的JSON数组，每个元素对应一个输入标题。
注意：只输出JSON数组，不要有任何其他文字。"""

    @classmethod
    def load(cls, prompts_file: Optional[str] = None) -> Tuple[str, str]:
        """
        从外部Markdown文件加载Prompts
        
        Args:
            prompts_file: Prompts文件路径，默认使用类属性PROMPTS_FILE
            
        Returns:
            (单条分析prompt, 批量分析prompt)
        """
        if prompts_file is None:
            prompts_file = cls.PROMPTS_FILE
        
        # 尝试多个可能的路径
        possible_paths = [
            prompts_file,
            os.path.join("common/process", prompts_file),
            os.path.join("..", prompts_file),
            os.path.join("../..", prompts_file),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                try:
                    return cls._load_from_file(path)
                except Exception as e:
                    logger.warning(f"从 {path} 加载Prompts失败: {e}")
                    continue
        
        # 所有路径都失败，使用默认Prompts
        logger.warning(f"无法找到Prompts文件，使用默认Prompts")
        return cls.DEFAULT_SYSTEM_PROMPT, cls.DEFAULT_BATCH_SYSTEM_PROMPT
    
    @classmethod
    def _load_from_file(cls, prompts_file: str) -> Tuple[str, str]:
        """
        从文件加载Prompts
        
        Args:
            prompts_file: Prompts文件路径
            
        Returns:
            (单条分析prompt, 批量分析prompt)
        """
        with open(prompts_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 解析单条分析Prompt
        single_prompt = cls._extract_section(content, "单条分析模式")
        if not single_prompt:
            raise ValueError("无法在llm_prompts.md中找到'单条分析模式'的System Prompt")
        
        # 解析批量分析Prompt
        batch_prompt = cls._extract_section(content, "批量分析模式")
        if not batch_prompt:
            raise ValueError("无法在llm_prompts.md中找到'批量分析模式'的System Prompt")
        
        logger.info(f"成功加载Prompts文件: {prompts_file}")
        return single_prompt, batch_prompt
    
    @classmethod
    def _extract_section(cls, content: str, section_name: str) -> Optional[str]:
        """
        从Markdown内容中提取指定section的System Prompt
        
        Args:
            content: Markdown文件内容
            section_name: section名称（如"单条分析模式"）
            
        Returns:
            System Prompt文本，未找到则返回None
        """
        # 查找section标题
        section_pattern = rf"##\s*{re.escape(section_name)}.*?\n###\s*System Prompt\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(section_pattern, content, re.DOTALL)
        
        if not match:
            return None
        
        prompt = match.group(1).strip()
        return prompt
