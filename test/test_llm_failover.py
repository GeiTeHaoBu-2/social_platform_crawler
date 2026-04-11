"""
测试LLM故障转移功能
模拟主模型失败，验证自动切换到备选模型
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.process.llm_client import LLMClient
from common.utils.logging_config import logger


def test_failover():
    """测试故障转移功能"""
    print("=" * 70)
    print("测试: LLM多模型故障转移")
    print("=" * 70)
    
    # 配置：主模型使用无效key，强制失败
    config = {
        'primary': {
            'api_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
            'api_key': 'invalid_key_for_testing',  # 无效key，会触发失败
            'model': 'qwen-turbo',
            'timeout': 10,
        },
        'backup_1': {
            'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
            'api_key': 'sk-test-backup1',  # 可能也是无效的
            'model': 'Pro/deepseek-ai/DeepSeek-R1',
            'timeout': 10,
        },
        'backup_2': {
            'api_url': 'https://open.bigmodel.cn/api/paas/v4/chat/completions',
            'api_key': 'test-backup2',
            'model': 'glm-4-flash',
            'timeout': 10,
        },
        'failover': {
            'max_retries': 2,  # 连续失败2次后切换
            'auto_recover': True,
        }
    }
    
    print("\n1. 初始化LLMClient")
    client = LLMClient(config)
    
    print("\n2. 查看初始状态")
    status = client.get_status()
    print(f"   当前模型: {status['current_model']}")
    print(f"   可用模型: {status['available_models']}")
    print(f"   故障转移: 连续失败{config['failover']['max_retries']}次后切换")
    
    print("\n3. 发起请求（预期会触发故障转移）")
    messages = [
        {"role": "system", "content": "你是一个助手"},
        {"role": "user", "content": "你好"}
    ]
    
    result = client.chat(messages)
    
    print("\n4. 查看最终状态")
    status = client.get_status()
    print(f"   当前模型: {status['current_model']}")
    print(f"   当前模型名称: {status['current_model_name']}")
    print(f"   连续失败次数: {status['consecutive_failures']}")
    print(f"   切换历史: {status['switch_history']}")
    
    if result:
        print(f"\n5. 请求成功，结果: {result[:100]}...")
    else:
        print(f"\n5. 请求失败（预期行为，因为配置的都是无效key）")
    
    print("\n" + "=" * 70)
    print("测试完成")
    print("=" * 70)


def test_with_real_config():
    """使用真实配置测试"""
    print("\n" + "=" * 70)
    print("测试: 使用真实配置文件")
    print("=" * 70)
    
    try:
        from common.config.settings import LLM_CONFIG
        
        print("\n1. 从settings加载配置")
        print(f"   主模型: {LLM_CONFIG.get('primary', {}).get('model', '未配置')}")
        print(f"   备选1: {LLM_CONFIG.get('backup_1', {}).get('model', '未配置')}")
        print(f"   备选2: {LLM_CONFIG.get('backup_2', {}).get('model', '未配置')}")
        
        print("\n2. 初始化LLMClient")
        client = LLMClient(LLM_CONFIG)
        
        print("\n3. 发起测试请求")
        messages = [
            {"role": "system", "content": "分析以下热搜的情感倾向、类型分类和相关话题"},
            {"role": "user", "content": "测试: 今天天气不错"}
        ]
        
        result = client.chat(messages, temperature=0.3)
        
        if result:
            print(f"\n4. 请求成功！")
            print(f"   结果: {result[:200]}...")
        else:
            print(f"\n4. 请求失败，检查日志了解详情")
        
        # 查看状态
        status = client.get_status()
        print(f"\n5. 最终状态")
        print(f"   当前模型: {status['current_model']}")
        print(f"   切换历史: {len(status['switch_history'])} 次")
        
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='测试LLM故障转移')
    parser.add_argument('--real', action='store_true', help='使用真实配置测试')
    args = parser.parse_args()
    
    if args.real:
        test_with_real_config()
    else:
        test_failover()
