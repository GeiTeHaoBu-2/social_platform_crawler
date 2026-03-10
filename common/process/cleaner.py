# 数据清洗模块
class Cleaner:
    def __init__(self):
        """
        初始化清洗器
        """
        pass

    def clean(self, raw_data):
        """
        数据清洗方法。
        主要功能：对抓取到的杂乱文本进行规范化处理（去除两端空格等）
        绝对不在这里删除 url，因为下游的 Redis 和 MySQL base 表还需要它！
        """
        for item in raw_data:
            # 真正的清洗：去除标题可能自带的无用空格或换行
            if item.title:
                item.title = item.title.strip()

            if item.url:
                item.url = item.url.strip()

        return raw_data