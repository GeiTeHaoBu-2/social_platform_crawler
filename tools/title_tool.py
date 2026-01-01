import requests
from bs4 import BeautifulSoup
import re
import json

# 1. 请求页面（确保Cookie有效、页面加载完成）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Cookie": "SINAGLOBAL=8561365396085.397.1765357522520; ALF=02_1767971925; SCF=AvUjt31lrwVY0_7Qg8l3tetG2Y4ixa1jPg1s9Uz0qiR8k-NLjayKQnitO8eEZ0RqXQD_Ilcu27lZHz9z9FCyhUM.; SUB=_2A25EPf8FDeRhGeFJ41oU-CvMzDuIHXVnM37NrDV8PUJbkNAYLU3gkW1NfvAsCjA-lvfgAMILnsggSg8iYCMkz6VK; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WFm2BdFQxr7PVATg3GWDoyy5NHD95QNS0nRSKnfehMNWs4Dqc_ei--ciK.fi-z7i--Ri-88i-2pi--4iK.4i-2Ei--Xi-isi-2pi--Ni-88i-2peKzEeEH8SC-4eFHFSFH8SEHFBCHWBCH81FHFxCHFe5tt; UOR=,,www.doubao.com; _s_tentry=-; Apache=6760023834022.405.1765546677184; ULV=1765546677202:3:3:3:6760023834022.405.1765546677184:1765458978175"
}
url = "https://s.weibo.com/weibo?q=%23%E4%B8%9C%E5%8C%97%E9%9B%A8%E5%A7%90%E8%BD%AC%E4%B8%96%E8%B4%A6%E5%8F%B7%E8%A2%AB%E5%85%B3%E9%97%AD%23&t=31&band_rank=1&Refer=top"
response = requests.get(url, headers=headers)
response.encoding = response.apparent_encoding  # 解决中文乱码
soup = BeautifulSoup(response.text, "lxml")
print(soup)
print("="*50)
tiezi_list = soup.find('div',class_="card-wrap")
print(tiezi_list.text)

# 验证页面是否正常加载
print("页面标题：", soup.find('title').get_text())
print("="*50)
