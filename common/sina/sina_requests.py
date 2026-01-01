import requests
import json

# 微博热搜API（需抓包确认最新接口）
url = "https://weibo.com/ajax/side/hotSearch"

# 请求头（需替换为自己的Cookie，从浏览器F12抓包获取）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie": "XSRF-TOKEN=j5b5Dysk2FJq4Vp5oncQF0Fk; _s_tentry=-; Apache=8561365396085.397.1765357522520; SINAGLOBAL=8561365396085.397.1765357522520; ULV=1765357522526:1:1:1:8561365396085.397.1765357522520:; ALF=02_1767971925; SCF=AvUjt31lrwVY0_7Qg8l3tetG2Y4ixa1jPg1s9Uz0qiR8k-NLjayKQnitO8eEZ0RqXQD_Ilcu27lZHz9z9FCyhUM.; SUB=_2A25EPf8FDeRhGeFJ41oU-CvMzDuIHXVnM37NrDV8PUJbkNAYLU3gkW1NfvAsCjA-lvfgAMILnsggSg8iYCMkz6VK; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WFm2BdFQxr7PVATg3GWDoyy5NHD95QNS0nRSKnfehMNWs4Dqc_ei--ciK.fi-z7i--Ri-88i-2pi--4iK.4i-2Ei--Xi-isi-2pi--Ni-88i-2peKzEeEH8SC-4eFHFSFH8SEHFBCHWBCH81FHFxCHFe5tt; WBPSESS=LNHbo63NlvO3HPtqYCaXrd__wT7Jejv5gI4uQwmA1jpfVAZpIxO8IOWmZthntBUZ1Vi0slaniuapvvCy6raA7ZcnnDakKqBRRavb0LdvcbRdLt3CsEnjKMhr-of-X4qQRrXUDN3ZGGxfUG7x85TzwA==",
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