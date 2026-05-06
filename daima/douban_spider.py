# 文件: douban_spider.py
import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import os


class DoubanSpider:
    def __init__(self):
        self.base_url = "https://movie.douban.com/top250"
        self.headers_pool = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'},
            {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'},
        ]
        self.session = requests.Session()
        self.movies_data = []

    def get_response(self, url, retries=3):
        """发送请求，包含异常处理和重试机制"""
        for i in range(retries):
            try:
                headers = random.choice(self.headers_pool)
                response = self.session.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return response
                elif response.status_code in [403, 429]:
                    print(f"请求被限制 (状态码: {response.status_code})，等待后重试...")
                    time.sleep(random.uniform(5, 10))  # 遇到限制时延长等待时间
                else:
                    print(f"请求失败 (状态码: {response.status_code})，重试中...")
            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}，重试中...")
            time.sleep(random.uniform(2, 5))  # 重试前的等待
        print(f"达到最大重试次数，放弃请求: {url}")
        return None

    def parse_list_page(self, soup):
        """解析列表页，提取单部电影的基础信息（适配新版豆瓣结构）"""
        movie_items = soup.find_all('div', class_='item')  # 这个通常没变
        for rank, item in enumerate(movie_items, start=1):
            movie = {}
            # 排名
            movie['rank'] = rank

            # 标题 (中英)
            title_span = item.find('span', class_='title')
            movie['title_cn'] = title_span.text.strip()

            # 英文标题在下一个 sibling span，且 class 可能是 'title' 或没有特定 class，这里用通用方法
            en_span = title_span.find_next_sibling('span')
            movie['title_en'] = ""
            if en_span and '/' in en_span.text:
                # 通常英文名在 '/' 之后
                parts = en_span.text.split('/', 1)
                if len(parts) > 1:
                    movie['title_en'] = parts[1].strip()

            movie['full_title'] = f"{movie['title_cn']} {movie['title_en']}".strip()

            # 评分
            # 注意：新版豆瓣评分通常在 <span class="rating_num"> 下
            rating_span = item.find('span', class_='rating_num')
            movie['rating'] = rating_span.text.strip() if rating_span else "暂无评分"

            # 评价人数
            # 注意：新版结构中，评价人数通常在 star div/p 的下一个 span，或者直接是文本
            # 我们直接通过文本查找 "人评价" 来定位
            star_div = item.find('div', class_='star') or item.find('p', class_='star')  # 兼容 div 或 p
            if star_div:
                # 获取所有文本，然后用正则或字符串查找
                star_text = star_div.get_text()
                import re
                match = re.search(r'(\d+)人评价', star_text)
                if match:
                    movie['votes'] = int(match.group(1))
                else:
                    movie['votes'] = 0
            else:
                movie['votes'] = 0

            # 导演/主演 (通常在 <p class=""> 标签里)
            # 在豆瓣新版中，info 通常是一个没有特定 class 的 p 标签，位于 header 之后
            info_p = item.find('div', class_='bd').find('p')
            movie['director_actor'] = info_p.get_text(strip=True) if info_p else "未知"

            # 简介 (inq)
            inq_span = item.find('span', class_='inq')
            movie['intro'] = inq_span.text.strip() if inq_span else "暂无简介"

            # 详情链接
            link_a = item.find('div', class_='pic').find('a')
            movie['detail_url'] = link_a['href'] if link_a else ""

            self.movies_data.append(movie)
    def crawl(self):
        """主爬取流程"""
        print("开始爬取豆瓣电影Top250列表...")
        for page in range(10):  # 爬取10页
            start = page * 25
            url = f"{self.base_url}?start={start}"
            print(f"正在爬取第 {page + 1} 页: {url}")

            response = self.get_response(url)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                self.parse_list_page(soup)
                # 随机延时，模拟人类行为
                time.sleep(random.uniform(1, 4))
            else:
                print(f"第 {page + 1} 页爬取失败，跳过。")

        print(f"列表页爬取完成，共获取 {len(self.movies_data)} 条数据。")
        return self.movies_data

    def save_to_csv(self, filename='douban_top250_base.csv'):
        """将基础数据保存到CSV文件"""
        if not self.movies_data:
            print("没有数据可保存。")
            return

        fieldnames = ['rank', 'title_cn', 'title_en', 'full_title', 'rating', 'votes', 'director_actor', 'intro',
                      'detail_url']
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.movies_data)
        print(f"基础数据已保存到 {filename}")


spider = DoubanSpider()
spider.crawl()
spider.save_to_csv()