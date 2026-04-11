"""
模块名称: llm_client.py
模块职责: LLM API 客户端，支持多模型故障转移

故障转移策略:
- 主模型连续失败 max_retries 次后，自动切换到备选模型
- 支持两级备选模型 (backup_1, backup_2)
- 每个请求周期自动尝试回退到主模型
"""
import json
import re
import time
from typing import List, Dict, Any, Optional
import requests
from common.utils.logging_config import logger


class LLMClient:
    """
    LLM API 客户端（支持多模型故障转移）
    
    使用示例:
        config = {
            'primary': {'api_url': '...', 'api_key': '...', 'model': '...', 'timeout': 30},
            'backup_1': {'api_url': '...', 'api_key': '...', 'model': '...', 'timeout': 30},
            'backup_2': {'api_url': '...', 'api_key': '...', 'model': '...', 'timeout': 30},
            'failover': {'max_retries': 2, 'auto_recover': True}
        }
        client = LLMClient(config)
        result = client.chat(messages)  # 自动处理故障转移
    """
    
    # 默认API配置
    DEFAULT_API_URL = "https://api.openai.com/v1/chat/completions"
    DEFAULT_MODEL = "gpt-3.5-turbo"
    DEFAULT_TIMEOUT = 30
    DEFAULT_MAX_RETRIES = 2
    
    def __init__(self, api_config: Dict[str, Any]):
        """
        初始化LLM客户端
        
        Args:
            api_config: API配置字典，支持多模型配置:
                - primary: 主模型配置
                - backup_1: 备选模型1配置
                - backup_2: 备选模型2配置
                - failover: 故障转移配置 {max_retries, auto_recover}
        """
        # 提取故障转移配置
        failover_config = api_config.get('failover', {})
        self.max_retries = failover_config.get('max_retries', self.DEFAULT_MAX_RETRIES)
        self.auto_recover = failover_config.get('auto_recover', True)
        
        # 初始化所有模型配置
        self.models = {}
        model_order = ['primary', 'backup_1', 'backup_2']
        
        for model_name in model_order:
            if model_name in api_config:
                self.models[model_name] = self._init_model_config(api_config[model_name], model_name)
        
        if not self.models:
            # 兼容旧配置格式
            self.models['primary'] = self._init_model_config(api_config, 'primary')
        
        # 当前使用的模型
        self.current_model = 'primary'
        self.consecutive_failures = 0
        
        # 记录模型切换历史
        self.switch_history = []
        
        logger.info(f"🤖 LLM Client初始化完成")
        logger.info(f"   主模型: {self.models.get('primary', {}).get('model', 'unknown')}")
        logger.info(f"   备选模型1: {self.models.get('backup_1', {}).get('model', '未配置')}")
        logger.info(f"   备选模型2: {self.models.get('backup_2', {}).get('model', '未配置')}")
        logger.info(f"   故障转移: 连续失败{self.max_retries}次后切换")
    
    def _init_model_config(self, config: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """初始化单个模型配置"""
        return {
            'name': model_name,
            'api_url': config.get('api_url', self.DEFAULT_API_URL),
            'api_key': config.get('api_key', ''),
            'model': config.get('model', self.DEFAULT_MODEL),
            'timeout': config.get('timeout', self.DEFAULT_TIMEOUT),
            'headers': {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.get('api_key', '')}"
            }
        }
    
    def _get_next_model(self) -> Optional[str]:
        """获取下一个可用的模型"""
        model_order = ['primary', 'backup_1', 'backup_2']
        current_idx = model_order.index(self.current_model) if self.current_model in model_order else -1
        
        # 尝试后续的模型
        for i in range(current_idx + 1, len(model_order)):
            next_model = model_order[i]
            if next_model in self.models:
                return next_model
        
        return None
    
    def _switch_model(self, reason: str):
        """切换到下一个可用模型"""
        next_model = self._get_next_model()
        
        if next_model:
            old_model = self.current_model
            self.current_model = next_model
            self.consecutive_failures = 0
            
            switch_info = {
                'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                'from': old_model,
                'to': next_model,
                'reason': reason
            }
            self.switch_history.append(switch_info)
            
            logger.warning(f"🔄 [LLM模型切换] {old_model} -> {next_model}")
            logger.warning(f"   原因: {reason}")
            logger.warning(f"   新模型: {self.models[next_model]['model']}")
        else:
            logger.error(f"❌ [LLM故障转移失败] 没有可用的备选模型")
            logger.error(f"   已尝试: {list(self.models.keys())}")
    
    def _try_recover_primary(self):
        """尝试回退到主模型（每个周期调用一次）"""
        if self.auto_recover and self.current_model != 'primary' and 'primary' in self.models:
            logger.info(f"🔄 [LLM自动恢复] 尝试回退到主模型...")
            self.current_model = 'primary'
            self.consecutive_failures = 0
            logger.info(f"✅ [LLM自动恢复] 已切换回主模型: {self.models['primary']['model']}")
    
    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3, 
             max_tokens: int = 2000) -> Optional[str]:
        """
        调用LLM API进行对话（支持自动故障转移）
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            API返回的内容或None
        """
        # 每个新请求周期尝试恢复主模型
        self._try_recover_primary()
        
        # 最多尝试所有可用模型
        attempted_models = []
        
        while True:
            model_config = self.models.get(self.current_model)
            if not model_config:
                logger.error(f"❌ [LLM错误] 当前模型 {self.current_model} 未配置")
                return None
            
            attempted_models.append(self.current_model)
            
            # 执行请求
            result = self._do_chat_request(model_config, messages, temperature, max_tokens)
            
            if result is not None:
                # 请求成功
                if self.consecutive_failures > 0:
                    logger.info(f"✅ [LLM恢复] {self.current_model} 请求成功，重置失败计数")
                self.consecutive_failures = 0
                return result
            
            # 请求失败
            self.consecutive_failures += 1
            logger.warning(f"⚠️  [LLM失败] {self.current_model} 连续失败 {self.consecutive_failures}/{self.max_retries} 次")
            
            # 检查是否需要切换模型
            if self.consecutive_failures >= self.max_retries:
                self._switch_model(f"连续失败{self.max_retries}次")
                
                # 如果已经尝试了所有模型，返回None
                if self.current_model in attempted_models:
                    logger.error(f"❌ [LLM错误] 所有模型都尝试失败: {attempted_models}")
                    return None
            else:
                # 同一模型重试前等待一小段时间
                wait_time = 1 * self.consecutive_failures
                logger.info(f"⏳  [LLM重试] 等待{wait_time}秒后重试...")
                time.sleep(wait_time)
    
    def _do_chat_request(self, model_config: Dict[str, Any], 
                         messages: List[Dict[str, str]], 
                         temperature: float, max_tokens: int) -> Optional[str]:
        """
        执行单次API请求
        
        Returns:
            成功返回内容，失败返回None
        """
        if not model_config.get('api_key'):
            logger.error(f"❌ [LLM错误] {model_config['name']} API密钥未配置")
            return None
        
        payload = {
            "model": model_config['model'],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            logger.debug(f"[LLM请求] {model_config['name']} ({model_config['model']})")
            
            response = requests.post(
                model_config['api_url'],
                headers=model_config['headers'],
                json=payload,
                timeout=model_config['timeout']
            )
            
            # 处理HTTP错误
            if response.status_code == 429:
                logger.warning(f"⚠️  [LLM限流] {model_config['name']} Token耗尽或请求过频 (429)")
                return None
            elif response.status_code == 401:
                logger.error(f"❌ [LLM认证失败] {model_config['name']} API密钥无效 (401)")
                return None
            elif response.status_code >= 500:
                logger.warning(f"⚠️  [LLM服务端错误] {model_config['name']} 状态码: {response.status_code}")
                return None
            
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            logger.debug(f"[LLM响应] {model_config['name']} 成功")
            return content.strip()
            
        except requests.exceptions.Timeout:
            logger.warning(f"⏱️  [LLM超时] {model_config['name']} 请求超时({model_config['timeout']}s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️  [LLM请求异常] {model_config['name']}: {e}")
            return None
        except (KeyError, json.JSONDecodeError) as e:
            logger.error(f"❌ [LLM解析失败] {model_config['name']}: {e}")
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
    
    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态信息"""
        return {
            'current_model': self.current_model,
            'current_model_name': self.models.get(self.current_model, {}).get('model', 'unknown'),
            'consecutive_failures': self.consecutive_failures,
            'available_models': list(self.models.keys()),
            'switch_history': self.switch_history[-5:]  # 最近5次切换
        }
