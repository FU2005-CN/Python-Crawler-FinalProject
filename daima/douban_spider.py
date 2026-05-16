# -*- coding: utf-8 -*-
"""
豆瓣TOP250爬虫（成员A完整版）
基础：requests + BeautifulSoup（列表页）
进阶：Selenium（详情页：年份/片长/类型/IMDb/短评/海报）
反爬：随机User-Agent、请求延时1-4秒、异常重试、无头浏览器隐藏特征
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
import random
import csv
import os
import re
import pymysql

# ==================== 配置区域 ====================
MYSQL_USER = "root"
MYSQL_PASSWORD = "123456"          # 请修改为你的 MySQL 密码
MYSQL_HOST = "127.0.0.1"

# 海报保存目录
POSTER_DIR = "movie_posters"
os.makedirs(POSTER_DIR, exist_ok=True)

# User-Agent 池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# ==================== 数据库操作 ====================
def init_database():
    """创建数据库和扩展后的表（如果不存在）"""
    db = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, charset="utf8mb4")
    cursor = db.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS douban_movie CHARACTER SET utf8mb4")
    cursor.execute("USE douban_movie")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS top250 (
        id INT PRIMARY KEY AUTO_INCREMENT,
        movie_rank INT,
        title_cn VARCHAR(255),
        title_en VARCHAR(500),
        score VARCHAR(50),
        vote_num VARCHAR(50),
        director TEXT,
        actor TEXT,
        intro TEXT,
        year VARCHAR(20),
        duration VARCHAR(50),
        genre VARCHAR(255),
        imdb VARCHAR(50),
        comments TEXT,
        poster_path TEXT,
        link TEXT
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    db.commit()
    cursor.close()
    db.close()
    print("数据库/表初始化完成（已存在则跳过）")

def clear_table():
    """清空 top250 表，重置自增 ID"""
    db = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database="douban_movie", charset="utf8mb4")
    cursor = db.cursor()
    cursor.execute("TRUNCATE TABLE top250")
    db.commit()
    cursor.close()
    db.close()
    print("已清空 top250 表，本次爬取将存入全新数据。")

def save_to_db(item):
    """保存单条完整数据到 MySQL"""
    db = pymysql.connect(host=MYSQL_HOST, user=MYSQL_USER, password=MYSQL_PASSWORD, database="douban_movie", charset="utf8mb4")
    cursor = db.cursor()
    sql = """
    INSERT INTO top250 (movie_rank, title_cn, title_en, score, vote_num, director, actor, intro,
                        year, duration, genre, imdb, comments, poster_path, link)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(sql, (
        item["排名"], item["中文标题"], item["外文标题"], item["评分"], item["评价人数"],
        item["导演"], item["主演"], item["简介"], item["年份"], item["片长"],
        item["类型"], item["IMDb"], item["短评"], item["海报路径"], item["详情链接"]
    ))
    db.commit()
    cursor.close()
    db.close()

# ==================== CSV 保存 ====================
def save_to_csv(item):
    """追加写入 CSV（字段与数据库一致）"""
    filename = "豆瓣TOP250完整数据.csv"
    file_exists = os.path.exists(filename)
    fieldnames = ["排名", "中文标题", "外文标题", "评分", "评价人数", "导演", "主演", "简介",
                  "年份", "片长", "类型", "IMDb", "短评", "海报路径", "详情链接"]
    with open(filename, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(item)

# ==================== 海报下载（方案一：携带Cookie+Referer） ====================
def download_poster(img_url, title, driver):
    """携带 Selenium 的 Cookie 和完整请求头下载海报，支持断点续传"""
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    poster_path = os.path.join(POSTER_DIR, f"{safe_title}.jpg")
    if os.path.exists(poster_path):
        print(f"    海报已存在，跳过：{poster_path}")
        return poster_path

    # 从 Selenium driver 中获取 cookies，转为 requests 可用格式
    cookies = driver.get_cookies()
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])

    # 完整请求头（Referer 必须，否则 418）
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": "https://movie.douban.com/",
        "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    try:
        resp = session.get(img_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            with open(poster_path, "wb") as f:
                f.write(resp.content)
            print(f"    ✅ 海报下载成功：{poster_path}")
            return poster_path
        else:
            print(f"    ❌ 海报下载失败 HTTP {resp.status_code}")
            return ""
    except Exception as e:
        print(f"    ❌ 海报下载异常：{e}")
        return ""

# ==================== 基础模块：requests 列表页爬取 ====================
def fetch_list_page(url):
    """发送请求，带重试机制，返回 BeautifulSoup 对象"""
    for retry in range(3):
        try:
            headers = {"User-Agent": random.choice(USER_AGENTS)}
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
            elif resp.status_code in (403, 429):
                print(f"    触发反爬 {resp.status_code}，等待 5 秒后重试...")
                time.sleep(5)
                continue
            else:
                print(f"    HTTP {resp.status_code}，重试 {retry+1}/3")
        except Exception as e:
            print(f"    请求异常：{e}，重试 {retry+1}/3")
        time.sleep(2)
    return None


def parse_list_page(soup):
    movies = []
    items = soup.select("div.item")
    for item in items:
        # 排名
        rank_elem = item.select_one("em")
        rank = rank_elem.text.strip() if rank_elem else ""
        # 中文标题
        title_cn_elem = item.select_one("span.title")
        title_cn = title_cn_elem.text.strip() if title_cn_elem else ""
        # 外文标题
        other_elem = item.select_one("span.other")
        title_en = other_elem.text.strip().replace("/", "").strip() if other_elem else ""
        # 评分
        score_elem = item.select_one("span.rating_num")
        score = score_elem.text.strip() if score_elem else ""
        # 评价人数（使用正则从整个 item 文本中提取）
        item_text = item.get_text()
        vote_match = re.search(r'(\d+(?:,\d+)*)人评价', item_text)
        vote_num = vote_match.group(0) if vote_match else ""   # 如 "3286590人评价"
        # 简介
        inq_elem = item.select_one("span.inq")
        intro_short = inq_elem.text.strip() if inq_elem else "无"
        # 详情链接
        link_elem = item.select_one("a")
        link = link_elem["href"] if link_elem else ""

        # 从底部信息提取导演、主演、年份
        bd_p = item.select_one("div.bd p")
        if bd_p:
            bd_text = bd_p.text.strip()
            director_match = re.search(r'导演:\s*(.*?)(?:主演:|$)', bd_text)
            director = director_match.group(1).strip() if director_match else ""
            actor_match = re.search(r'主演:\s*(.*?)(?:\n|$)', bd_text)
            actor = actor_match.group(1).strip() if actor_match else ""
            year_match = re.search(r'(\d{4})', bd_text)
            year = year_match.group(1) if year_match else ""
        else:
            director = actor = year = ""

        movies.append({
            "排名": rank,
            "中文标题": title_cn,
            "外文标题": title_en,
            "评分": score,
            "评价人数": vote_num,
            "导演": director,
            "主演": actor,
            "简介": intro_short,
            "年份": year,
            "片长": "",
            "类型": "",
            "IMDb": "",
            "短评": "",
            "海报路径": "",
            "详情链接": link
        })
    return movies

def crawl_top250_list():
    """使用 requests 爬取全部10页列表页，返回所有电影基础信息"""
    all_movies = []
    for page in range(10):
        url = f"https://movie.douban.com/top250?start={page*25}"
        print(f"\n📄 列表页第 {page+1}/10 页：{url}")
        soup = fetch_list_page(url)
        if not soup:
            print(f"  ❌ 第 {page+1} 页请求失败，跳过")
            continue
        page_movies = parse_list_page(soup)
        print(f"  ✅ 获取 {len(page_movies)} 条记录")
        all_movies.extend(page_movies)
        # 随机延时 1-4 秒
        time.sleep(random.uniform(1, 4))
    print(f"\n🎯 列表页共获取 {len(all_movies)} 部电影（应为250）")
    return all_movies

# ==================== 进阶模块：Selenium 详情页抓取 ====================
def setup_selenium_driver():
    """配置无头 Chrome，隐藏自动化特征"""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")          # 无头模式
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)
    # 随机 User-Agent
    chrome_options.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()),
                              options=chrome_options)
    # 隐藏 webdriver 属性
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def extract_detail_info(driver, movie):
    """使用 Selenium 提取详情页的额外字段：年份、片长、类型、IMDb、短评、海报"""
    url = movie["详情链接"]
    title = movie["中文标题"]
    print(f"\n🎬 正在处理详情页：{title}")

    try:
        driver.get(url)
        # 等待页面核心内容加载
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "content")))

        # 随机延时，模拟人类行为
        time.sleep(random.uniform(2, 4))

        # ---------- 1. 基本信息（年份、片长、类型、IMDb）----------
        info_text = ""
        try:
            info_elem = driver.find_element(By.ID, "info")
            info_text = info_elem.text
        except:
            pass

        # 年份
        year_match = re.search(r'(\d{4})', info_text)
        if year_match:
            movie["年份"] = year_match.group(1)
        # 片长
        duration_match = re.search(r'(\d+)分钟', info_text)
        if duration_match:
            movie["片长"] = f"{duration_match.group(1)}分钟"
        # 类型
        genre_match = re.search(r'类型:\s*(.*?)(?:\n|$)', info_text)
        if genre_match:
            movie["类型"] = genre_match.group(1).strip()
        # IMDb
        imdb_elem = driver.find_elements(By.XPATH, '//span[text()="IMDb:"]/following-sibling::a')
        if imdb_elem:
            imdb_url = imdb_elem[0].get_attribute("href")
            imdb_match = re.search(r'tt(\d+)', imdb_url)
            movie["IMDb"] = f"tt{imdb_match.group(1)}" if imdb_match else imdb_url
        else:
            movie["IMDb"] = "无"

        # ---------- 2. 导演和主演（列表页可能不全，用详情页覆盖）----------
        try:
            directors = driver.find_elements(By.XPATH, '//a[@rel="v:directedBy"]')
            if directors:
                movie["导演"] = directors[0].text.strip()
        except:
            pass
        try:
            actors = driver.find_elements(By.XPATH, '//a[@rel="v:starring"]')
            if actors:
                movie["主演"] = " / ".join([a.text.strip() for a in actors[:5]])
        except:
            pass

        # ---------- 3. 完整简介（可能需点击“展开全部”）----------
        try:
            expand_btn = driver.find_element(By.XPATH, '//a[contains(text(),"展开全部")]')
            driver.execute_script("arguments[0].click();", expand_btn)
            time.sleep(1)
        except:
            pass
        try:
            all_intro = driver.find_element(By.CSS_SELECTOR, "span.all")
            intro_full = all_intro.text.strip()
            if "©豆瓣" in intro_full:
                intro_full = intro_full.split("©豆瓣")[0].strip()
            movie["简介"] = intro_full
        except:
            # 回退到 v:summary
            try:
                summary = driver.find_element(By.XPATH, '//span[@property="v:summary"]')
                movie["简介"] = summary.text.strip()
            except:
                pass

        # ---------- 4. 海报下载（携带 Cookie + Referer）----------
        try:
            poster_img = driver.find_element(By.ID, "mainpic").find_element(By.TAG_NAME, "img")
            img_url = poster_img.get_attribute("src")
            if img_url:
                movie["海报路径"] = download_poster(img_url, title, driver)   # 传入 driver
        except Exception as e:
            print(f"    ⚠️ 海报获取失败：{e}")

        # ---------- 5. 热门短评（至少15条，含评论者、评分、内容、时间）----------
        comments = []
        try:
            # 滚动到评论区，触发加载
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            # 点击“加载更多”（如果存在）
            try:
                more_btn = driver.find_element(By.CSS_SELECTOR, "a.more")
                driver.execute_script("arguments[0].click();", more_btn)
                print("    → 点击“加载更多”短评")
                time.sleep(2)
            except:
                pass

            # 再次滚动，确保评论完全加载
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

            # 定位评论项（支持新旧两种结构）
            comment_items = driver.find_elements(By.CSS_SELECTOR, ".comment-item, .comment")
            print(f"    → 找到 {len(comment_items)} 条短评容器")

            for node in comment_items[:20]:  # 取前20条，确保够15
                try:
                    # 评论者
                    user = node.find_element(By.CSS_SELECTOR, ".comment-info a").text.strip()
                    # 评分（星级）
                    rating_cls = node.find_element(By.CSS_SELECTOR, ".comment-info .rating").get_attribute("class")
                    star_match = re.search(r'allstar(\d+)', rating_cls)
                    rating = int(star_match.group(1)) // 10 if star_match else 0
                    star_str = "★" * rating if rating > 0 else "未评分"
                    # 评论内容
                    content = node.find_element(By.CSS_SELECTOR, ".short, .comment-content").text.strip()
                    # 评论时间
                    time_elem = node.find_elements(By.CSS_SELECTOR, ".comment-time")
                    ctime = time_elem[0].text.strip() if time_elem else ""
                    comments.append(f"{user}({star_str})：{content}【{ctime}】")
                except:
                    continue

            if comments:
                movie["短评"] = " | ".join(comments[:15])
                print(f"    ✅ 获取到 {len(comments)} 条短评，已保存前15条")
            else:
                movie["短评"] = "无短评"
                print("    ⚠️ 未获取到短评")

        except Exception as e:
            print(f"    ❌ 短评抓取异常：{e}")
            movie["短评"] = "短评抓取失败"

    except Exception as e:
        print(f"    ❌ 详情页处理失败：{e}")

    return movie

def enrich_with_selenium(movies):
    """使用 Selenium 批量补充所有电影的详情信息"""
    driver = setup_selenium_driver()
    try:
        for i, movie in enumerate(movies):
            print(f"\n【进度 {i+1}/{len(movies)}】")
            movie = extract_detail_info(driver, movie)
            # 每处理完一部，立即保存到 CSV 和 MySQL
            save_to_csv(movie)
            save_to_db(movie)
            # 随机延时，降低被封风险
            time.sleep(random.uniform(3, 6))
    finally:
        driver.quit()

# ==================== 主函数 ====================
def main():
    # 1. 初始化 CSV（删除旧文件，全新生成）
    csv_file = "豆瓣TOP250完整数据.csv"
    if os.path.exists(csv_file):
        os.remove(csv_file)
        print(f"已删除旧 {csv_file}，本次运行将重新生成。")

    # 2. 初始化数据库（建库建表）
    init_database()
    clear_table()

    # 3. 基础爬取：requests 列表页
    print("\n" + "="*60)
    print("阶段一：requests + BeautifulSoup 爬取列表页")
    print("="*60)
    movies = crawl_top250_list()

    # 4. 进阶爬取：Selenium 详情页（年份、片长、类型、IMDb、短评、海报）
    print("\n" + "="*60)
    print("阶段二：Selenium 爬取详情页（动态加载）")
    print("="*60)
    enrich_with_selenium(movies)

    print("\n✅ 全部完成！数据已保存至 CSV 和 MySQL。")
    print(f"📁 海报保存在目录：{POSTER_DIR}/")

if __name__ == "__main__":
    main()