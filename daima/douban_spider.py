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
from selenium.common.exceptions import WebDriverException


class DoubanSpider:
    def __init__(self):
        self.base_url = "https://movie.douban.com/top250"
        self.headers_pool = [
            {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://movie.douban.com/'
            },
            {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://movie.douban.com/'
            },
        ]
        self.session = requests.Session()
        self.movies_data = []

        self.img_dir = "douban_posters"
        os.makedirs(self.img_dir, exist_ok=True)

        # -------------------- 关键：降低反爬 + 稳定连接 --------------------
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--blink-settings=imagesEnabled=true")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=self.chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 15)

    def get_response(self, url, retries=3):
        for i in range(retries):
            try:
                headers = random.choice(self.headers_pool)
                response = self.session.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return response
                elif response.status_code in [403, 429]:
                    print(f"请求受限 {response.status_code}，等待重试...")
                    time.sleep(random.uniform(8, 12))
                else:
                    time.sleep(random.uniform(2, 5))
            except requests.exceptions.RequestException as e:
                print(f"请求异常: {e}")
                time.sleep(random.uniform(2, 5))
        print(f"放弃请求: {url}")
        return None

    def parse_list_page(self, soup):
        movie_items = soup.find_all('div', class_='item')
        for rank, item in enumerate(movie_items, start=1):
            movie = {}
            movie['rank'] = rank

            title_span = item.find('span', class_='title')
            movie['title_cn'] = title_span.text.strip() if title_span else ""
            other_span = item.find('span', class_='other')
            movie['title_en'] = other_span.text.strip().replace(' / ', '') if other_span else ""
            movie['full_title'] = f"{movie['title_cn']} {movie['title_en']}".strip()

            rating_span = item.find('span', class_='rating_num')
            movie['rating'] = rating_span.text.strip() if rating_span else "暂无评分"

            star_div = item.find('div', class_='star')
            movie['votes'] = 0
            if star_div:
                match = re.search(r'(\d+)', star_div.get_text())
                movie['votes'] = int(match.group(1)) if match else 0

            info_p = item.find('div', class_='bd').find('p')
            movie['basic_info'] = " ".join(info_p.get_text(strip=True).split()) if info_p else "未知"

            inq_span = item.find('span', class_='inq')
            movie['intro'] = inq_span.text.strip() if inq_span else "暂无简介"

            link_a = item.find('div', class_='pic').find('a')
            movie['detail_url'] = link_a['href'] if link_a else ""

            movie['year'] = ""
            movie['duration'] = ""
            movie['genre'] = ""
            movie['imdb_rating'] = ""
            movie['poster_url'] = ""
            movie['comments'] = []

            self.movies_data.append(movie)

    # -------------------- 修复：详情页更稳 + 自动重连 + 降低反爬 --------------------
    def fetch_detail_with_selenium(self, movie, retry=2):
        if not movie['detail_url']:
            return
        for attempt in range(retry):
            try:
                print(f"  -> Selenium正在抓取详情页: {movie['title_cn']}")
                self.driver.get(movie['detail_url'])
                time.sleep(random.uniform(2.5, 4))

                # 1. 年份、片长、类型
                try:
                    info_text = self.wait.until(EC.presence_of_element_located((By.ID, "info"))).text
                    movie['year'] = re.search(r'(\d{4})', info_text).group(1) if re.search(r'(\d{4})', info_text) else ""
                    movie['duration'] = re.search(r'(\d+)分钟', info_text).group(1) + "分钟" if re.search(r'(\d+)分钟', info_text) else ""
                    genre_match = re.search(r'类型:\s*(.*?)(?=\n|上映日期|$)', info_text, re.S)
                    movie['genre'] = genre_match.group(1).strip().replace('\n', '/') if genre_match else ""
                except:
                    print("    -> 提取详情基础信息失败")

                # 2. IMDb评分
                try:
                    movie['imdb_rating'] = self.driver.find_element(By.XPATH, '//span[text()="IMDb"]/following-sibling::span').text.strip()
                except:
                    movie['imdb_rating'] = "无"

                # 3. 海报（修复：data-src兼容 + 不被屏蔽）
                try:
                    poster_img = self.wait.until(EC.presence_of_element_located((By.ID, "mainpic"))).find_element(By.TAG_NAME, "img")
                    poster_url = poster_img.get_attribute("data-src") or poster_img.get_attribute("src")
                    movie['poster_url'] = poster_url
                    self.download_image(poster_url, movie['title_cn'])
                except:
                    print("    -> 提取海报失败")

                # 4. 短评（稳很多）
                try:
                    comments = []
                    while len(comments) < 15:
                        items = self.driver.find_elements(By.CSS_SELECTOR, ".comment-item")
                        for c in items:
                            if len(comments) >= 15:
                                break
                            try:
                                author = c.find_element(By.CSS_SELECTOR, ".comment-info a").text
                                score_cls = c.find_element(By.CSS_SELECTOR, ".comment-info span").get_attribute("class")
                                score = re.search(r'allstar(\d+)', score_cls)
                                score = int(score.group(1)) // 10 if score else 0
                                content = c.find_element(By.CLASS_NAME, "short").text
                                ctime = c.find_element(By.CLASS_NAME, "comment-time").get_attribute("title")
                                comments.append(f"{author}({score}星): {content} [{ctime}]")
                            except:
                                continue
                        try:
                            more = self.driver.find_element(By.CSS_SELECTOR, "#comments-section .more")
                            self.driver.execute_script("arguments[0].click();", more)
                            time.sleep(random.uniform(2, 3))
                        except:
                            break
                    movie['comments'] = comments[:15]
                except Exception as e:
                    print(f"    -> 提取短评失败: {e}")

                return

            except WebDriverException as e:
                print(f"  -> Selenium连接异常（重试{attempt+1}/{retry}）: {e}")
                time.sleep(random.uniform(5, 8))
            except Exception as e:
                print(f"  -> 未知错误: {e}")
                break

    def download_image(self, url, title):
        try:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            file_extension = url.split('.')[-1].split('?')[0]
            file_name = f"{safe_title}.{file_extension}"
            save_path = os.path.join(self.img_dir, file_name)

            if os.path.exists(save_path):
                print(f"    -> 图片已存在，跳过下载: {safe_title}")
                return True

            print(f"    -> 正在下载海报: {safe_title}")
            img_response = self.session.get(url, headers=random.choice(self.headers_pool), timeout=15)
            if img_response.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(img_response.content)
                return True
        except Exception as e:
            print(f"    -> 图片下载失败: {e}")
            return False

    def crawl(self):
        print("开始爬取豆瓣电影Top250列表...")
        for page in range(10):
            start = page * 25
            url = f"{self.base_url}?start={start}"
            print(f"正在爬取第 {page + 1} 页: {url}")

            response = self.get_response(url)
            if response:
                soup = BeautifulSoup(response.text, 'html.parser')
                self.parse_list_page(soup)
                time.sleep(random.uniform(2, 4))
            else:
                print(f"第 {page + 1} 页爬取失败，跳过。")

        print(f"列表页爬取完成，共获取 {len(self.movies_data)} 条数据。")
        if not self.movies_data:
            return []

        print("\n开始使用 Selenium 进入详情页抓取深度数据及海报...")
        for idx, movie in enumerate(self.movies_data, 1):
            print(f"\n【{idx}/{len(self.movies_data)}】{movie['title_cn']}")
            self.fetch_detail_with_selenium(movie)
            time.sleep(random.uniform(3, 5))  # 超重要：防10054

        print("\n//所有数据及海报抓取完成！")
        return self.movies_data

    def save_to_csv(self, filename='douban_top250_advanced.csv'):
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
        print(f"\n完整数据已保存到 {filename}")

    def close(self):
        if self.driver:
            self.driver.quit()
            print("\nSelenium 浏览器驱动已关闭。")


if __name__ == '__main__':
    spider = DoubanSpider()
    try:
        spider.crawl()
        spider.save_to_csv()
    finally:
        spider.close()