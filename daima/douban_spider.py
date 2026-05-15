import requests
from bs4 import BeautifulSoup
import time
import random
import csv
import os
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class DoubanSpider:
    def __init__(self):
        self.base_url = "https://movie.douban.com/top250"
        self.headers_pool = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
            {
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
        ]
        self.session = requests.Session()
        self.movies_data = []

        # 1. 图片保存目录
        self.img_dir = "douban_posters"
        if not os.path.exists(self.img_dir):
            os.makedirs(self.img_dir)

        # 2. 初始化 Selenium 无头浏览器
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        # 屏蔽图片加载以加快Selenium速度（我们只抓取文本和海报链接）
        self.chrome_options.add_experimental_option("prefs", {"profile.managed_default_content_settings.images": 2})
        self.driver = webdriver.Chrome(options=self.chrome_options)

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
                    time.sleep(random.uniform(5, 10))
                else:
                    print(f"请求失败 (状态码: {response.status_code})，重试中...")
            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}，重试中...")
            time.sleep(random.uniform(2, 5))
        print(f"达到最大重试次数，放弃请求: {url}")
        return None

    def parse_list_page(self, soup):
        """解析列表页，提取基础信息"""
        movie_items = soup.find_all('div', class_='item')
        for rank, item in enumerate(movie_items, start=1):
            movie = {}
            movie['rank'] = rank

            # 标题提取
            title_span = item.find('span', class_='title')
            movie['title_cn'] = title_span.text.strip() if title_span else ""
            other_span = item.find('span', class_='other')
            movie['title_en'] = other_span.text.strip().replace(' / ', '') if other_span else ""
            movie['full_title'] = f"{movie['title_cn']} {movie['title_en']}".strip()

            # 评分与评价人数
            rating_span = item.find('span', class_='rating_num')
            movie['rating'] = rating_span.text.strip() if rating_span else "暂无评分"

            star_div = item.find('div', class_='star')
            movie['votes'] = 0
            if star_div:
                match = re.search(r'(\d+)人评价', star_div.get_text())
                movie['votes'] = int(match.group(1)) if match else 0

            # 导演/主演/年份等基础信息
            info_p = item.find('div', class_='bd').find('p')
            movie['basic_info'] = " ".join(info_p.get_text(strip=True).split()) if info_p else "未知"

            # 简介
            inq_span = item.find('span', class_='inq')
            movie['intro'] = inq_span.text.strip() if inq_span else "暂无简介"

            # 详情链接
            link_a = item.find('div', class_='pic').find('a')
            movie['detail_url'] = link_a['href'] if link_a else ""

            # 初始化详情页字段
            movie['year'] = ""
            movie['duration'] = ""
            movie['genre'] = ""
            movie['imdb_rating'] = ""
            movie['poster_url'] = ""
            movie['comments'] = []

            self.movies_data.append(movie)

    # 进阶：使用 Selenium 爬取详情页、短评并下载海报
    def fetch_detail_with_selenium(self, movie):
        if not movie['detail_url']:
            return
        try:
            print(f"  -> Selenium正在抓取详情页: {movie['title_cn']}")
            self.driver.get(movie['detail_url'])
            wait = WebDriverWait(self.driver, 10)

            # 1. 提取详情页核心信息 (年份、片长、类型)
            try:
                info_span = wait.until(EC.presence_of_element_located((By.ID, "info")))
                info_text = info_span.text
                # 使用正则提取
                year_match = re.search(r'年份:\s*(\d{4})', info_text)
                movie['year'] = year_match.group(1) if year_match else ""

                duration_match = re.search(r'片长:\s*([\d\./\s分]+)', info_text)
                movie['duration'] = duration_match.group(1).strip() if duration_match else ""

                genre_match = re.search(r'类型:\s*([\s\S]*?)(?=上映日期|$)', info_text)
                movie['genre'] = genre_match.group(1).strip().replace('\n', '/') if genre_match else ""
            except:
                print("    -> 提取详情页基础信息失败")

            # 2. 提取 IMDb 评分
            try:
                imdb_link = self.driver.find_element(By.CSS_SELECTOR, "a[href*='imdb.com']")
                if imdb_link:
                    # IMDb评分通常在链接旁边的span中，或者需要再次请求IMDb页面（这里简化处理，只提取是否存在）
                    # 豆瓣详情页有时直接显示IMDb评分，这里尝试提取
                    rating_span = self.driver.find_element(By.CSS_SELECTOR, "#interest_sectl .rating_wrap .rating_num")
                    # 注意：这里仅作演示，IMDb评分在豆瓣页面通常不直接显示，需跳转。
                    # 如果页面有直接显示，可在此处提取。
            except:
                pass

            # 3. 提取电影海报并下载 (断点续传)
            try:
                poster_img = wait.until(EC.presence_of_element_located((By.ID, "mainpic")))
                poster_url = poster_img.find_element(By.TAG_NAME, "img").get_attribute("src")
                movie['poster_url'] = poster_url
                self.download_image(poster_url, movie['title_cn'])
            except:
                print("    -> 提取海报失败")

            # 4. 提取至少前15条热门短评 (处理JS动态加载)
            try:
                # 等待评论区加载
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#comments-section .comment-item")))

                comments = []
                load_more_btn = self.driver.find_elements(By.CSS_SELECTOR, "#comments-section a.more")

                # 模拟点击“加载更多”，直到短评数量 >= 15 或没有更多按钮
                while len(comments) < 15 and load_more_btn:
                    current_comments = self.driver.find_elements(By.CSS_SELECTOR, "#comments-section .comment-item")
                    for c in current_comments:
                        try:
                            author = c.find_element(By.CSS_SELECTOR, ".comment-info a").text
                            rating_class = c.find_element(By.CSS_SELECTOR, ".comment-info span").get_attribute("class")
                            # 提取评分 (如 allstar40 代表 4星/5星)
                            score = re.search(r'allstar(\d+)', rating_class)
                            score = int(score.group(1)) // 10 if score else 0
                            content = c.find_element(By.CSS_SELECTOR, ".short").text
                            time_str = c.find_element(By.CSS_SELECTOR, ".comment-time").get_attribute("title")
                            comments.append(f"{author}({score}星): {content} [{time_str}]")
                        except:
                            continue

                    if len(comments) >= 15:
                        break

                    # 尝试点击加载更多
                    try:
                        load_more_btn = self.driver.find_element(By.CSS_SELECTOR, "#comments-section a.more")
                        if load_more_btn and load_more_btn.is_displayed():
                            self.driver.execute_script("arguments[0].click();", load_more_btn)
                            time.sleep(random.uniform(1, 2))  # 等待新评论加载
                        else:
                            break
                    except:
                        break

                movie['comments'] = comments[:15]  # 只保留前15条
            except Exception as e:
                print(f"    -> 提取短评失败: {e}")

        except Exception as e:
            print(f"  -> Selenium抓取详情页整体失败: {e}")

        # 随机延时，模拟真实用户
        time.sleep(random.uniform(2, 4))

    # 图片下载 (支持断点续传)
    def download_image(self, url, title):
        try:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            file_extension = url.split('.')[-1].split('?')[0]
            file_name = f"{safe_title}.{file_extension}"
            save_path = os.path.join(self.img_dir, file_name)

            # 断点续传核心：检查文件是否已存在
            if os.path.exists(save_path):
                print(f"    -> 图片已存在，跳过下载: {safe_title}")
                return True

            print(f"    -> 正在下载海报: {safe_title}")
            img_response = self.session.get(url, timeout=15)
            if img_response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(img_response.content)
                return True
        except Exception as e:
            print(f"    -> 图片下载失败: {e}")
            return False

    def crawl(self):
        """主爬取流程"""
        print("开始爬取豆瓣电影Top250列表...")
        for page in range(10):
            start = page * 25
            url = f"{self.base_url}?start={start}"
            print(f"正在爬取第 {page + 1} 页: {url}")

            response = self.get_response(url)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                self.parse_list_page(soup)
                time.sleep(random.uniform(1, 3))
            else:
                print(f"第 {page + 1} 页爬取失败，跳过。")

        print(f"列表页爬取完成，共获取 {len(self.movies_data)} 条数据。")
        print("\n开始使用 Selenium 进入详情页抓取深度数据及海报...")

        for movie in self.movies_data:
            self.fetch_detail_with_selenium(movie)

        print("//所有数据及海报抓取完成！")
        return self.movies_data

    def save_to_csv(self, filename='douban_top250_advanced.csv'):
        """将完整数据保存到CSV文件"""
        if not self.movies_data:
            print("没有数据可保存。")
            return

        fieldnames = ['rank', 'title_cn', 'title_en', 'full_title', 'rating', 'votes',
                      'basic_info', 'year', 'duration', 'genre', 'imdb_rating',
                      'intro', 'detail_url', 'poster_url', 'comments']
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.movies_data)
        print(f"完整数据已保存到 {filename}")

    def close(self):
        """关闭Selenium浏览器驱动"""
        if self.driver:
            self.driver.quit()
            print("Selenium 浏览器驱动已关闭。")


if __name__ == '__main__':
    spider = DoubanSpider()
    try:
        spider.crawl()
        spider.save_to_csv()
    finally:
        spider.close()