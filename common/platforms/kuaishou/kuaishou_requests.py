import requests
from bs4 import BeautifulSoup
import re
import json

# 1. 请求页面（确保Cookie有效、页面加载完成）
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Cookie": "kpf=PC_WEB; clientid=3; did=web_e2c58877ab8a010a0681fcc01a47398d; kwpsecproductname=kuaishou-vision; kwpsecproductname=kuaishou-vision; didv=1765431524903; ktrace-context=1|MS44Nzg0NzI0NTc4Nzk2ODY5LjE4MTQyOTE0LjE3NjU0MzE1MzAwMjMuMTM1MjgxOA==|MS44Nzg0NzI0NTc4Nzk2ODY5Ljg0NTE5MjM0LjE3NjU0MzE1MzAwMjMuMTM1MjgxOQ==|0|webservice-user-growth-node|webservice|true|src-Js; kpn=KUAISHOU_VISION; bUserId=1000535629428; userId=5191405574; ud=5191405574; language=zh-CN; kwssectoken=WQzGz5ARxesAUsAzf41CwBvA2lULrEqzZZC4pVloz6mQRQSVfc7ETxgX2gU27NaBYzm5ejVW0suap73w68g/qw==; kwscode=221e9b74fd391ece5b7009f34d24ccb1e330605d70e7fcab17150fd8c6f4f944; kuaishou.server.webday7_st=ChprdWFpc2hvdS5zZXJ2ZXIud2ViZGF5Ny5zdBKwAdfl6ApK4_MR65aABneYJilsBc0rRIs5k0VWb-0RJGWrDofxECPbccosqmoE3erMaVvdSz2ensp5qW-Z5By4P7NK1P0BFzqRS93Gua97t6oqGxmnrrgM-I0fq_k6KMuLgR8wn2MkQz4clMqYkjkqgI51XEQ5g7kVdrbhXt6r31Az4w1h68tWEOgBQYpxwitFZB8XMQRNBlYgxKmqaRKVQ8XFkYJwr-ggfJN2EZD5WubWGhKnKVNp11MmMNF2Nrbv1tNDD3siINxHUJ7ts52lN0OE7UeeF3ZIyYKVzvycW3uOUdK69jnDKAUwAQ; kuaishou.server.webday7_ph=ab10c0bf66761d82b87790c50389034bf5f0; kwfv1=PnGU+9+Y8008S+nH0U+0mjPf8fP08f+98f+nLlwnrIP9+Sw/ZFGfzY+eGlGf+f+e4SGfbYP0QfGnLFwBLU80mYGAZ78emY+/ZMG9LhP/LUPALMweYS+/LlPBHl+fPA+9z0GnGU+A4DweWEGAHF8fcF8nQYPBL7+e40+9b0wBGMwBG7G0L7weWUPe+fP0L9PAHUG/DhGASf8fzjwBr7+eL7+I=="
}
url = "https://www.kuaishou.com/brilliant"
response = requests.get(url, headers=headers)
response.encoding = response.apparent_encoding  # 解决中文乱码
soup = BeautifulSoup(response.text, "lxml")

# 验证页面是否正常加载
print("页面标题：", soup.find('title').get_text())
print("="*50)

# 2. 查找包含__APOLLO_STATE__的script标签
target_script = None
for script in soup.find_all("script"):
    script_text = script.text.strip()
    if "__APOLLO_STATE__" in script_text:
        target_script = script_text
        break

if not target_script:
    print("❌ 未找到Apollo状态数据，可能原因：")
    print("1. Cookie已失效，需重新获取")
    print("2. 页面为动态渲染，需改用Selenium")
else:
    # 3. 正则提取JSON主体（去除JS变量语法）
    pattern = r'window\.__APOLLO_STATE__\s*=\s*({.*?});'
    match = re.search(pattern, target_script, re.DOTALL)
    if not match:
        print("❌ 正则匹配Apollo数据失败")
    else:
        # 4. 清洗JSON并解析
        json_str = match.group(1).strip()
        # 修复JSON语法错误（末尾多余逗号）
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)

        try:
            apollo_data = json.loads(json_str)
            # 关键修复：数据实际在defaultClient层级中
            default_client = apollo_data.get("defaultClient", {})
            if not default_client:
                print("❌ 未找到defaultClient层级数据")
            else:
                # 5. 定位visionHotRank数据（注意键的格式，取消多余转义）
                hot_rank_key = '$ROOT_QUERY.visionHotRank({"page":"brilliant"})'
                hot_rank_data = default_client.get(hot_rank_key, {})
                print(f"📌 原始hot_rank_data结构：{hot_rank_data.keys() if hot_rank_data else '空'}")
                hot_items = hot_rank_data.get("items", [])

                if not hot_items:
                    print("❌ 未提取到热榜数据，可尝试打印defaultClient的keys确认")
                    # 可选：打印所有key，排查键名偏差
                    # print("defaultClient所有key：", list(default_client.keys())[:5])
                else:
                    print(f"✅ 共提取到{len(hot_items)}条热榜数据")
                    print("="*50)

                    # 6. 遍历热榜，关联具体信息
                    for idx, item in enumerate(hot_items):
                        item_id = item.get("id")
                        item_detail = default_client.get(item_id, {})  # 同样从defaultClient取详情
                        rank = item_detail.get("rank", idx)
                        title = item_detail.get("name", "未知标题")
                        hot_value = item_detail.get("hotValue", "未知热度")
                        tag_type = item_detail.get("tagType", "无标签")

                        # 格式化输出（置顶/新标签特殊标注）
                        if tag_type == "置顶":
                            print(f"【置顶】{title}")
                        elif tag_type == "新":
                            print(f"第{rank}条（新）：{title} | 热度：{hot_value}")
                        else:
                            print(f"第{rank}条：{title} | 热度：{hot_value}")

        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败：{str(e)}")