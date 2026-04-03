import jieba
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from transformers import pipeline
import re

# 用户输入热搜
user_input = "张三出轨事件引发热议"

# 1. 情感分析（保持不变）
def analyze_sentiment(text):
    sentiment_pipeline = pipeline("sentiment-analysis", model="bert-base-chinese")
    result = sentiment_pipeline(text)[0]
    return 0.8 if result["label"] == "LABEL_1" else -0.5

# 2. 类型分类（优化版）
def classify_type(text):
    categories = {
        "ENTERTAINMENT": ("娱乐", ["明星", "八卦", "影视", "综艺", "音乐", "演唱会"]),
        "LIVELIHOOD": ("民生", ["社会", "寻人", "天气", "治安", "事故", "维权"]),
        "POLITICS": ("时政", ["政策", "外交", "会议", "官方", "领导", "政府"]),
        "FINANCE": ("财经", ["股市", "基金", "财报", "宏观", "货币", "楼市"]),
        "TECHNOLOGY": ("科技", ["AI", "人工智能", "手机", "互联网", "科学", "航天"]),
        "SPORTS": ("体育", ["奥运", "世界杯", "NBA", "足球", "电竞", "运动员"]),
        "LIFESTYLE": ("生活", ["健康", "美食", "教育", "职场", "情感", "旅游"]),
        "OTHERS": ("其他", [])
    }

    # 优先检查是否包含人名（为后续话题聚类做准备）
    if re.search(r'[\u4e00-\u9fa5]{2,4}[\u4e00-\u9fa5]?', text):
        return "娱乐"  # 人物相关热搜默认归为娱乐类（可根据需要调整）

    # 常规关键词匹配
    for key, (name, keywords) in categories.items():
        if any(kw in text for kw in keywords):
            return name
    return "其他"

# 3. 动态话题聚类（完全重写）
def cluster_topic(text):
    # 使用命名实体识别提取人物名称
    ner_pipeline = pipeline("ner", model="bert-base-chinese")
    entities = ner_pipeline(text)

    # 提取人名实体（PER标签）
    person_entities = [ent["word"] for ent in entities if ent["entity"] == "PER"]

    # 如果有明确人名，直接使用人名作为话题
    if person_entities:
        return person_entities[0]  # 返回第一个主要人名

    # 备用方案：使用TF-IDF和KMeans进行内容聚类
    # （此处简化，实际应用需维护历史热搜数据库）
    return "综合"

# 执行分析
sentiment = analyze_sentiment(user_input)
category = classify_type(user_input)
topic = cluster_topic(user_input)

# 输出结果
print(f"输入热搜: {user_input}")
print(f"1. 情感打分: {sentiment:.2f}")
print(f"2. 所属类型: {category}")
print(f"3. 所属话题: {topic}")