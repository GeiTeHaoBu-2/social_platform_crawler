"""
配置示例文件 - 复制此文件为 settings.py 并填入你的实际配置
"""

# MySQL数据库配置
DB = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': 'your_password_here',
    'database': 'social_platforms_analysis',
    'charset': 'utf8mb4'
}

# Redis配置
REDIS = {
    'host': '127.0.0.1',
    'port': 6379,
    'db': 0,
    'decode_responses': True
}

# Kafka配置
KAFKA = {
    'bootstrap_servers': ['127.0.0.1:9092'],
    'topic': 'weibo_hot_search'
}

# LLM分析器配置
ANALYZER = {
    'api_key': 'your_api_key_here',
    'api_url': 'https://api.siliconflow.cn/v1/chat/completions',
    'model': 'Pro/deepseek-ai/DeepSeek-R1',
    'max_workers': 3,
    'batch_size': 10,
    'temperature': 0.3,
    'use_cache': True
}

# 爬虫配置
CRAWLER = {
    'sleep_seconds': 60
}

# 微博请求头
WEIBO_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Cookie': 'your_cookie_here',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

WEIBO_URL = 'https://s.weibo.com/top/summary'

# 统一配置字典
CONFIG = {
    'DB': DB,
    'REDIS': REDIS,
    'KAFKA': KAFKA,
    'ANALYZER': ANALYZER,
    'CRAWLER': CRAWLER
}
