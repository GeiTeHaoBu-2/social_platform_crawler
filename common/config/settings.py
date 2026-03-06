# 存放所有外部依赖的配置


#把 localhost 换成 127.0.0.1，这在很多操作系统的底层网络解析中速度更快，且不易报 socket 错误。
REDIS_CONFIG = {
    'host': '127.0.0.1',
    'port': 6379,
    'data_db': 0,
    'deduplication_db': 1,
    'password': '',  # 没有密码保持为空

    # 【新增】：多平台 Key 命名空间映射
    'keys': {
        'weibo': 'platform:weibo:realtime_board',
        'zhihu': 'platform:zhihu:realtime_board',
        'baidu': 'platform:baidu:realtime_board'
    },

    # 【新增】：缓存过期时间（秒），默认 10 分钟
    'expire_time': 600
}

MYSQL_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'root',
    'password': '',
    'database': 'social_platforms_analysis',
    'charset': 'utf8mb4',
    'weibo_table': {
        'chs':'weibo_current_hot_search',
        'hhs':'weibo_history_hot_search'
    },
    'zhihu_table': {
        'chs': 'zhihu_current_hot_search',
        'hhs': 'zhihu_history_hot_search'
    }
}

KAFKA_CONFIG = {
    'servers': ['localhost:9092'],
    'topics': {
        'weibo': 'weibo.hotsearch'
    }
}

WEIBO_URL = "https://s.weibo.com/top/summary"
WEIBO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": "SCF=Ajn0diikk2WYz_4OlN61z6NE471qVTDPHB3-9ylg7mOGIR4O1WbygPxIAm046YdPKXBE2vCjse4uEwNu1GecQF4.; SINAGLOBAL=5943957075602.887.1767002130326; SUB=_2AkMe9NFsf8NxqwFRmv8TzmnkZYx2zgrEieKoqCC3JRMxHRl-yT9yqnxetRB6NXT_g8rfkgQpmznj7chKev8TuQ3vK9V3; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9W59fZ02yYYTqEB73faZ8M7H; _s_tentry=passport.weibo.com; Apache=7196073902585.139.1772641885824; ULV=1772641885826:6:2:2:7196073902585.139.1772641885824:1772295095838",
    "Referer": "https://weibo.com/",
    "X-Requested-With": "XMLHttpRequest"
}
