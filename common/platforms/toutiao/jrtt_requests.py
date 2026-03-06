import requests
from bs4 import BeautifulSoup
import re
import json

# 1. 请求页面（确保Cookie有效、页面加载完成）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Cookie": "tt_webid=7582169319782991370; gfkadpd=24,6457; ttcid=dc447b3a84754f17802f334b9b570c2a42; local_city_cache=%E6%B7%B1%E5%9C%B3; s_v_web_id=verify_mizuku3p_nMhrLjvs_LBEn_460l_Bzny_zoW4tJcgiowl; _ga=GA1.1.269152260.1765361369; csrftoken=3c26a1f8c90d58604cedafe450e2c6a7; ttwid=1%7C_1kM4piJCs3QzWJ-zh1gmJFAClG10V6P6ooNHu3_sno%7C1765474821%7C67a22eeadb4e06d25c66ff990ce491de988ca82689c39f9b4a11ed6821a92282; _ga_QEHZPBE5HH=GS2.1.s1765474644$o5$g1$t1765474822$j49$l0$h0; tt_scid=zakCt0SzFVRwjU.RcvNUEL5cBS-UcFpPMcPgc-qelyDJqZP9tVrGFKnrx39yw1jR16c1"
}
url = "https://www.toutiao.com/"
response = requests.get(url, headers=headers)
response.encoding = response.apparent_encoding  # 解决中文乱码
soup = BeautifulSoup(response.text, "lxml")

# 验证页面是否正常加载
print("页面标题：", soup.find('title').get_text())
print("="*50)
print(soup)
# 查找所有 <a> 标签
all_links = soup.find_all('a', target="_blank" ,rel="noopener" ,class_="title")
# 定义正则表达式：匹配所有中文字符（\u4e00-\u9fa5是中文Unicode范围）
chinese_pattern = re.compile(r'[\u4e00-\u9fa5]+')

for link in all_links:
    # 1. 提取标签内的纯文本，并去除首尾空格
    raw_text = link.get_text(strip=True)
    # 2. 筛选出所有中文字符，拼接成完整字符串
    chinese_text = ''.join(chinese_pattern.findall(raw_text))
    # 3. 打印结果（过滤空字符串）
    if chinese_text:
        print(chinese_text)