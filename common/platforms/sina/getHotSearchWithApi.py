import requests
import json

#j抓包热搜页面的接口，直接调用内部接口
# 微博热搜API（需抓包确认最新接口）
url = "https://weibo.com/ajax/side/hotSearch"

# 请求头（需替换为自己的Cookie，从浏览器F12抓包获取）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": "SCF=Ajn0diikk2WYz_4OlN61z6NE471qVTDPHB3-9ylg7mOGIR4O1WbygPxIAm046YdPKXBE2vCjse4uEwNu1GecQF4.; SINAGLOBAL=5943957075602.887.1767002130326; SUB=_2AkMe9NFsf8NxqwFRmv8TzmnkZYx2zgrEieKoqCC3JRMxHRl-yT9yqnxetRB6NXT_g8rfkgQpmznj7chKev8TuQ3vK9V3; SUBP=0033WrSXqPxfM72-Ws9jqgMF55529P9D9W59fZ02yYYTqEB73faZ8M7H; ULV=1772641885826:6:2:2:7196073902585.139.1772641885824:1772295095838; XSRF-TOKEN=9gulwE1VYN14CXauUbOfN2b1; WBPSESS=PDVUzjtcUt2fIitQvMR4oQT3c1HEHvUiB6x5H3HTbTwO4B9gkbOweZyovIGB9WYdEkEcV4yJk0Pi2_GtZfFyssF4oxFvN4AWvd8QaKpGqZKkEJgceznHtfcL8ORydFzvT8AwvI14BxPE9BVuqJh22ZQpRq2kUFimGKHHoRpw930=",
    "Referer": "https://weibo.com/",
    "X-Requested-With": "XMLHttpRequest"
}

# 发送请求
response = requests.get(url, headers=headers)
if response.status_code == 200:
    data = json.loads(response.text)
    # 提取热搜数据
    hot_list = data.get("rdata", {}).get("realtime", [])
    for idx, hot in enumerate(hot_list, 1):
        print(f"第{idx}条：{hot.get('note')}（热度：{hot.get('num')}）")
else:
    print(f"请求失败：{response.status_code}，可能Cookie过期/IP被封")