from bs4 import BeautifulSoup
import requests

url = 'https://www.toutiao.com/'
response = requests.get(url)
response.encoding = 'utf-8'

if response.status_code == 200:
    soup = BeautifulSoup(response.text, 'lxml')

    title_content = soup.find('title')

    if title_content:
        print(title_content)
        print(title_content.get_text())
        print(title_content.string)
        print(title_content.text)
    else:
        print("未找到title标签")
else:
    print("请求失败，状态码：",response.status_code)
