# -*- coding: utf-8 -*-
import sys
import requests
import json
import time
import pymongo
import csv
import os
import re  # 用于清理HTML标签

# 连接MongoDB（若不需要可注释）
client = pymongo.MongoClient('localhost', 27017)
weibo = client['weibo']
comment_ = weibo['comment_']

# 请求头（替换为自己的有效Cookie）
headers = {
    "Cookie": '_T_WM=a9d0c8d78f9da2069ddff531625113ff; WEIBOCN_FROM=1110006030; SCF=AvUjt31lrwVY0_7Qg8l3tetG2Y4ixa1jPg1s9Uz0qiR8NbV_y8FFmWTpcTD4s_t7hBatEwnbfp-H_3NW_J6galk.; SUB=_2A25EOpKeDeRhGeBK6lcX-CjOwz6IHXVnOapWrDV6PUJbktAYLWPkkW1NR_3ccGkdYKLFt2TcDfuWYhFu-24zlMsB; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9W5KWiwMYwj8XkUh4G58jGbv5NHD95QcSh2fSonceonEWs4DqcjPHXDhCL.LxK-L1K-L122LxK-L1KeL1hnt; SSOLoginState=1765728974; ALF=1768320974; MLOGIN=1; XSRF-TOKEN=88d426; M_WEIBOCN_PARAMS=oid%3D4173028302302955%26luicode%3D20000061%26lfid%3D4173028302302955; mweibo_short_token=7c989fd584',
    "User-Agent": 'Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1'
}

# 微博评论API（缩小测试范围，避免无效请求）
url_comment = [
    f'https://m.weibo.cn/api/comments/show?id=5243694768982122&page={i}'
    for i in range(1, 100)  # 先爬1-9页测试，按需扩大
]

# CSV文件路径
path = os.path.join(os.getcwd(), "weibo.csv")
flag = 0

def clean_html_tags(text):
    """清理评论中的HTML标签、表情图片链接等冗余内容"""
    if not text:
        return ""
    # 移除HTML标签（<xxx>格式）
    text = re.sub(r'<[^>]+>', '', text)
    # 移除表情图片链接（https://face.t.sinajs.cn/...）
    text = re.sub(r'https://face\.t\.sinajs\.cn/[^ ]+', '', text)
    # 移除多余空格/换行
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_comment(url, writer):
    """获取单页评论并写入CSV（修复格式问题）"""
    global flag
    try:
        wb_data = requests.get(url, headers=headers, timeout=10)
        wb_data.raise_for_status()
        jsondata = wb_data.json()
        datas = jsondata.get('rdata', {}).get('rdata')

        if not datas:
            flag = 1
            print('无数据')
            return

        for data in datas:
            # 提取字段并处理空值/冗余内容
            created_at = data.get("created_at", "")
            like_counts = data.get("like_counts", 0)
            # 来源字段空值替换为"未知"
            source = data.get("source", "未知")
            username = data.get("user", {}).get("screen_name", "未知用户")
            # 清理评论中的HTML标签，去掉json.dumps避免重复引号
            comment = clean_html_tags(data.get("text", ""))

            # 写入CSV（csv.writer自动处理引号，无需手动转义）
            writer.writerow((username, created_at, source, comment, like_counts))

        print(f"成功爬取URL: {url}")

    except requests.exceptions.RequestException as e:
        print(f"请求失败: {url} | 错误: {str(e)}")
    except (KeyError, json.JSONDecodeError) as e:
        print(f"解析失败: {url} | 错误: {str(e)}")
    except Exception as e:
        print(f"未知错误: {url} | 错误: {str(e)}")

if __name__ == "__main__":
    # 打开CSV文件（utf-8-sig带BOM，newline=''避免换行问题）
    with open(path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.writer(csvfile)
        # 写入表头
        writer.writerow(('用户名', '发布时间', '来源', '评论内容', '点赞数'))

        i = 0
        # 遍历爬取
        for url in url_comment:
            get_comment(url, writer)
            time.sleep(0)  # 防反爬延迟
            print(f"已完成第 {i+1} 个URL")
            i += 1
            if flag:
                print("无更多评论，爬取结束。")
                break

    print(f"爬取完成！文件保存至: {path}")