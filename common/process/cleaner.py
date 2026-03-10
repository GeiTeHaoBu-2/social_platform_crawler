# 数据清洗模块
class Cleaner:
    def __init__(self):
        """
        初始化清洗器，可以在这里加载配置或初始化资源。
        """
        pass

    def clean(self, raw_data):
        """
        数据清洗方法。
        主要功能：
        1. 删除 url 字段（Redis 已保存完整数据，Kafka 只需传输核心字段）
        :param raw_data: 原始数据 (HotSearchItem 对象列表)
        :return: 清洗后的数据 (移除 url 后的 HotSearchItem 对象列表)
        """
        for item in raw_data:
            # 将 url 设为 None，to_dict() 时不会序列化
            item.url = None

        return raw_data
