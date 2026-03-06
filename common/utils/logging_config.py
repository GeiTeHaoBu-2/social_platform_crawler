import logging
import os
import sys


# 自定义彩色格式化器
class ColoredFormatter(logging.Formatter):
    # 定义颜色字典
    COLORS = {
        'DEBUG': '\033[94m',  # 蓝色
        'INFO': '\033[92m',  # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',  # 红色
        'CRITICAL': '\033[95m\033[1m',  # 紫色加粗
    }
    RESET = '\033[0m'  # 结束颜色

    def format(self, record):
        # 根据日志级别获取对应颜色，默认无色
        log_color = self.COLORS.get(record.levelname, self.RESET)

        # 将颜色代码拼接进格式字符串中
        # 这里的格式：时间 - 爬虫名字 - [级别] - 内容
        #format_str = f"{log_color}%(asctime)s - %(name)s - [%(levelname)s] - %(message)s{self.RESET}"
        format_str = f"{log_color}[%(levelname)s] - %(message)s{self.RESET}"

        # 动态创建对应的 Formatter 并格式化
        formatter = logging.Formatter(format_str, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


# 获取全局配置的日志级别
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# 1. 创建 Logger
logger = logging.getLogger('social_platform_crawler')
logger.setLevel(LOG_LEVEL)

# 2. 清理可能存在的旧 Handler（防止在 Jupyter 或多次导入时重复打印）
if logger.hasHandlers():
    logger.handlers.clear()

# 3. 创建控制台处理器，必须指定 sys.stdout，打破 IDE 的红色魔咒
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(LOG_LEVEL)

# 4. 把我们的彩色“滤镜”装到处理器上
console_handler.setFormatter(ColoredFormatter())

# 5. 把处理器挂载到 Logger 上
logger.addHandler(console_handler)

# 阻止日志向上一级父节点传播（防止被框架默认的处理器再次拦截打印）
logger.propagate = False

if __name__ == '__main__':
    # 你可以直接运行这个文件测试一下绚丽的效果！
    logger.debug('这是一条 DEBUG 级别的蓝色日志')
    logger.info('这是一条 INFO 级别的绿色日志')
    logger.warning('这是一条 WARNING 级别的黄色日志')
    logger.error('这是一条 ERROR 级别的红色日志')