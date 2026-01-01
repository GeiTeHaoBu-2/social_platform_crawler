import requests
import re
from bs4 import BeautifulSoup

session = requests.Session()


headers={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Cookie":"default-src * blob:;img-src * rdata: blob: resource: t.captcha.qq.com *.dun.163yun.com *.dun.163.com *.126.net *.nosdn.127.net nos.netease.com;connect-src * wss: blob: resource:;frame-src 'self' *.zhihu.com mailto: tel: weixin: *.vzuu.com mo.m.taobao.com getpocket.com note.youdao.com safari-extension://com.evernote.safari.clipper-Q79WDW8YH9 blob: mtt: zhihujs: captcha.guard.qcloud.com pos.baidu.com dup.baidustatic.com openapi.baidu.com wappass.baidu.com passport.baidu.com *.cme.qcloud.com vs-cdn.tencent-cloud.com t.captcha.qq.com *.dun.163yun.com *.dun.163.com *.126.net *.nosdn.127.net nos.netease.com;script-src 'self' blob: *.zhihu.com g.alicdn.com qzonestyle.gtimg.cn res.wx.qq.com open.mobile.qq.com 'unsafe-eval' unpkg.zhimg.com unicom.zhimg.com resource: zhihu-live.zhimg.com captcha.gtimg.com captcha.guard.qcloud.com pagead2.googlesyndication.com cpro.baidustatic.com pos.baidu.com dup.baidustatic.com i.hao61.net jsapi.qq.com 'nonce-f0bb4e52-aca9-458b-bda5-b6d24153a624' hm.baidu.com zz.bdstatic.com b.bdstatic.com imgcache.qq.com vs-cdn.tencent-cloud.com www.mangren.com www.yunmd.net zhihu.govwza.cn p.cnwza.cn beta-mini-app-static.jd.com ssl.captcha.qq.com t.captcha.qq.com *.dun.163yun.com *.dun.163.com *.126.net *.nosdn.127.net nos.netease.com;style-src 'self' 'unsafe-inline' *.zhihu.com unpkg.zhimg.com unicom.zhimg.com resource: captcha.gtimg.com www.mangren.com ssl.captcha.qq.com t.captcha.qq.com *.dun.163yun.com *.dun.163.com *.126.net *.nosdn.127.net nos.netease.com;font-src * rdata:;frame-ancestors *.zhihu.com *.realsee.com *.realsee.cn",
    "Referer":"https://www.zhihu.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Connection": "keep-alive"
}
session.get("https://www.zhihu.com/", headers=headers)

url = "https://www.zhihu.com/billboard"
response = session.get(url, headers=headers)
response.encoding = response.apparent_encoding  # 解决中文乱码
soup = BeautifulSoup(response.text, "lxml")

# 5. 打印结果（验证是否拿到真实页面）
print("响应状态码：", response.status_code)
print("响应文本长度：", len(response.text))  # 真实热榜页面长度远大于当前的几百字符
soup = BeautifulSoup(response.text, "lxml")
print("是否包含热榜标签：", bool(soup.find("div", class_="HotItem-content")))
