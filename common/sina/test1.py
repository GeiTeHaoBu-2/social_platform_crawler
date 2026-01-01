import requests

headers = {
    "Cookie": "_T_WM=a9d0c8d78f9da2069ddff531625113ff; WEIBOCN_FROM=1110006030; SCF=AvUjt31lrwVY0_7Qg8l3tetG2Y4ixa1jPg1s9Uz0qiR8NbV_y8FFmWTpcTD4s_t7hBatEwnbfp-H_3NW_J6galk.; SUB=_2A25EOpKeDeRhGeBK6lcX-CjOwz6IHXVnOapWrDV6PUJbktAYLWPkkW1NR_3ccGkdYKLFt2TcDfuWYhFu-24zlMsB; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9W5KWiwMYwj8XkUh4G58jGbv5NHD95QcSh2fSonceonEWs4DqcjPHXDhCL.LxK-L1K-L122LxK-L1KeL1hnt; SSOLoginState=1765728974; ALF=1768320974; MLOGIN=1; XSRF-TOKEN=88d426; M_WEIBOCN_PARAMS=oid%3D4173028302302955%26luicode%3D20000061%26lfid%3D4173028302302955; mweibo_short_token=7c989fd584",  # 替换成浏览器里能访问的Cookie
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 9_1 like Mac OS X) AppleWebKit/601.1.46 (KHTML, like Gecko) Version/9.0 Mobile/13B143 Safari/601.1"
}

# 测试page=3的接口
test_url = "https://m.weibo.cn/api/comments/show?id=5242971906641287&page=2"
# 发送请求，禁止重定向（避免被跳转到登录页）
response = requests.get(test_url, headers=headers, timeout=10, allow_redirects=False)

print("=== 调试信息 ===")
print(f"状态码：{response.status_code}")
print(f"响应内容类型：{response.headers.get('Content-Type')}")
print(f"原始返回内容：\n{response.text[:11500]}")  # 打印前500字符，避免内容过长