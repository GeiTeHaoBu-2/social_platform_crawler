"""
LLM分析器测试
测试LLM API连接和分析功能
"""
import sys
import logging
sys.path.insert(0, '.')

from common.process.llm_analyzer import LLMAnalyzer
from common.config.settings import CONFIG

# 配置日志级别为DEBUG以查看大模型返回结构
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


def test_llm():
    """测试LLM分析器"""
    print("=" * 50)
    print("LLM分析器测试")
    print("=" * 50)
    
    try:
        # 1. 检查配置
        print("\n[1/4] 检查配置...")
        analyzer_config = CONFIG['ANALYZER']
        
        if not analyzer_config.get('enabled'):
            print("✗ LLM未启用，请在settings.py中设置 enabled: True")
            return False
        
        if not analyzer_config.get('api_key'):
            print("✗ API Key未配置")
            return False
        
        print(f"✓ 配置正常")
        print(f"  - API URL: {analyzer_config.get('api_url', '默认')}")
        print(f"  - Model: {analyzer_config.get('model', '默认')}")
        
        # 2. 初始化分析器
        print("\n[2/4] 初始化分析器...")
        analyzer = LLMAnalyzer(analyzer_config)
        print("✓ 分析器初始化成功")
        print(f"  - System Prompt 长度: {len(analyzer.system_prompt)}")
        
        # 3. 测试单条分析
        print("\n[3/4] 测试单条分析...")
        test_title = "刘畊宏健身直播引发全民运动热潮"
        print(f"  测试标题: {test_title}")
        
        result = analyzer.analyze(test_title)
        print(f"✓ 分析结果:")
        print(f"  - 情感分数: {result.get('sentiment_score', 'N/A')}")
        print(f"  - 类型: {result.get('type_name', 'N/A')}")
        print(f"  - 话题: {result.get('topic_name', 'N/A')}")
        print(f"  - 关键词: {result.get('keywords', 'N/A')}")
        
        # 4. 测试批量分析
        print("\n[4/4] 测试批量分析...")
        test_titles = [
            "刘畊宏健身直播引发全民运动热潮",
            "吴亦凡官宣离婚引发关注",
            "股市今日大涨突破3000点"
        ]
        print(f"  测试{len(test_titles)}条批量分析...")
        
        results = analyzer.analyze_batch(test_titles)
        print(f"✓ 批量分析完成: {len(results)} 条结果")
        
        for i, (title, res) in enumerate(zip(test_titles, results)):
            print(f"  {i+1}. {title[:15]}... -> {res.get('topic_name', 'N/A')}")
        
        print("\n" + "=" * 50)
        print("✓ LLM测试全部通过!")
        print("=" * 50)
        return True
        
    except FileNotFoundError as e:
        print(f"✗ Prompts文件缺失: {e}")
        return False
    except Exception as e:
        print(f"✗ LLM测试失败: {e}")
        return False


if __name__ == "__main__":
    test_llm()
