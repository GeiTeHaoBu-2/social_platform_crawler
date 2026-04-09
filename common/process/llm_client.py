"""
模块名称: llm_client.py
模块职责: LLM API 客户端，处理HTTP请求和响应解析
"""
import json
import re
from typing import List, Dict, Any, Optional
import requests
from common.utils.logging_config import logger


class LLMClient:
    """LLM API 客户端"""
    
    # 默认API配置
    DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-3.5-turbo"
    DEFAULT_TIMEOUT = 30
    
    def __init__(self, api_config: Dict[str, Any]):
        """
        初始化LLM客户端
        
        Args:
            api_config: API配置字典，包含：
                - api_url: API端点地址
                - api_key: API密钥
                - model: 模型名称
                - timeout: 请求超时时间（秒）
        """
        self.api_url = api_config.get('api_url', self.DEFAULT_API_URL)
        self.api_key = api_config.get('api_key', '')
        self.model = api_config.get('model', self.DEFAULT_MODEL)
        self.timeout = api_config.get('timeout', self.DEFAULT_TIMEOUT)
        
        # 请求头
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        logger.info(f"LLM Client初始化完成，模型: {self.model}")
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, 
             max_tokens: int = 2000) -> Optional[str]:
        """
        调用LLM API进行对话
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            API返回的内容或None
        """
        if not self.api_key:
            logger.error("LLM API密钥未配置")
            return None
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = requests.post(
                self.api_url,
                headers=self.headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 调试：打印完整API响应
            logger.debug(f"LLM API原始响应:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
            
            content = result['choices'][0]['message']['content']
            
            # 调试：打印提取的content内容
            logger.debug(f"LLM返回的content内容:\n{content}")
            
            return content.strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"LLM API请求失败: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"LLM API响应解析失败: {e}")
            return None
    
    def parse_json_response(self, content: str) -> Optional[Any]:
        """
        解析API返回的JSON内容
        
        Args:
            content: API返回的文本内容
            
        Returns:
            解析后的对象（字典或列表）或None
        """
        try:
            # 尝试直接解析
            result = json.loads(content)
            logger.debug(f"JSON解析成功: {result}")
            return result
        except json.JSONDecodeError as e:
            logger.debug(f"直接JSON解析失败: {e}, 内容: {content[:200]}...")
            # 尝试从代码块中提取
            try:
                # 查找JSON代码块
                if '```json' in content:
                    json_str = content.split('```json')[1].split('```')[0].strip()
                    logger.debug(f"从```json代码块提取: {json_str[:100]}...")
                elif '```' in content:
                    json_str = content.split('```')[1].split('```')[0].strip()
                    logger.debug(f"从```代码块提取: {json_str[:100]}...")
                else:
                    # 尝试查找方括号或花括号包裹的内容
                    start = content.find('[') if '[' in content else content.find('{')
                    end = content.rfind(']') if '[' in content else content.rfind('}')
                    if start != -1 and end != -1:
                        json_str = content[start:end+1]
                        logger.debug(f"从方括号/花括号提取: {json_str[:100]}...")
                    else:
                        logger.error(f"无法找到JSON内容: {content[:200]}")
                        return None
                
                result = json.loads(json_str)
                logger.debug(f"代码块JSON解析成功: {result}")
                return result
            except (json.JSONDecodeError, IndexError) as e:
                logger.error(f"JSON解析失败: {e}, 内容: {content[:500]}")
                return None
