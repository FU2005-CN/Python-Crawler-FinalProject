#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Requests vs Scrapy 性能对比脚本
对比成员A的 requests 版本和 Scrapy 框架版本的爬取性能
"""

import os
import sys
import time
import subprocess
import json
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

# 设置中文显示
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

# 项目路径
PROJECT_ROOT = r'C:\Users\jxy04\PycharmProjects\PythonProject6\PythonProject13'
SCRAPY_DIR = os.path.join(PROJECT_ROOT, 'douban_scrapy')


# ==================== 1. Requests 版本测试 ====================
def run_requests_version(max_movies=50):
    """运行成员A的 requests 版本（仅列表页）"""
    print("\n" + "=" * 60)
    print("📡 正在运行 Requests 版本...")
    print("=" * 60)

    start_time = time.time()

    try:
        # 导入 douban_spider 中的函数
        sys.path.insert(0, PROJECT_ROOT)
        import douban_spider as spider

        # 临时修改配置，只爬取指定数量
        movies = []
        pages_needed = (max_movies + 24) // 25

        for page in range(min(pages_needed, 10)):
            url = f"https://movie.douban.com/top250?start={page * 25}"
            print(f"  爬取第 {page + 1} 页...")

            soup = spider.fetch_list_page(url)
            if soup:
                page_movies = spider.parse_list_page(soup)
                movies.extend(page_movies)
                print(f"    获取 {len(page_movies)} 条")

                if len(movies) >= max_movies:
                    movies = movies[:max_movies]
                    break

            time.sleep(random.uniform(1, 2))

        end_time = time.time()
        elapsed = end_time - start_time

        return {
            'name': 'Requests + BeautifulSoup',
            'version': '成员A版本',
            'time': elapsed,
            'movie_count': len(movies),
            'avg_time_per_movie': elapsed / len(movies) if movies else 0,
            'success': True
        }

    except Exception as e:
        print(f"  ❌ 运行失败: {e}")
        return {
            'name': 'Requests + BeautifulSoup',
            'version': '成员A版本',
            'time': 0,
            'movie_count': 0,
            'avg_time_per_movie': 0,
            'success': False,
            'error': str(e)
        }


# ==================== 2. Scrapy 版本测试 ====================
def run_scrapy_version(max_movies=50):
    """运行 Scrapy 版本（top250.py）"""
    print("\n" + "=" * 60)
    print("🕷️ 正在运行 Scrapy 版本...")
    print("=" * 60)

    start_time = time.time()

    # 计算需要的页数（每页25条）
    pages = (max_movies + 24) // 25

    try:
        # 运行 Scrapy 爬虫
        cmd = f'cd /d "{SCRAPY_DIR}" && scrapy crawl top250 -a max_pages={pages} -o data/scrapy_test.json:json -s LOG_LEVEL=ERROR'

        print(f"  执行命令: scrapy crawl top250 -a max_pages={pages}")

        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=SCRAPY_DIR
        )

        end_time = time.time()
        elapsed = end_time - start_time

        # 读取输出文件
        output_file = os.path.join(SCRAPY_DIR, 'data', 'scrapy_test.json')
        results = []

        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                try:
                    results = json.load(f)
                except:
                    results = []

        # 清理临时文件
        if os.path.exists(output_file):
            os.remove(output_file)

        return {
            'name': 'Scrapy 框架',
            'version': 'top250.py',
            'time': elapsed,
            'movie_count': len(results),
            'avg_time_per_movie': elapsed / len(results) if results else 0,
            'success': True
        }

    except subprocess.TimeoutExpired:
        print("  ❌ 运行超时")
        return {
            'name': 'Scrapy 框架',
            'version': 'top250.py',
            'time': 0,
            'movie_count': 0,
            'avg_time_per_movie': 0,
            'success': False,
            'error': '超时'
        }
    except Exception as e:
        print(f"  ❌ 运行失败: {e}")
        return {
            'name': 'Scrapy 框架',
            'version': 'top250.py',
            'time': 0,
            'movie_count': 0,
            'avg_time_per_movie': 0,
            'success': False,
            'error': str(e)
        }


# ==================== 3. 简化版 Requests 测试（纯列表页）====================
def run_simple_requests(max_movies=50):
    """简化版 Requests 爬虫（仅列表页，用于纯性能对比）"""
    print("\n" + "=" * 60)
    print("⚡ 正在运行简化版 Requests（纯列表页）...")
    print("=" * 60)

    import requests
    from bs4 import BeautifulSoup
    import random

    start_time = time.time()

    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    ]

    movies = []
    start = 0

    while len(movies) < max_movies:
        url = f'https://movie.douban.com/top250?start={start}'
        print(f"  爬取: {url}")

        try:
            headers = {'User-Agent': random.choice(user_agents)}
            resp = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(resp.text, 'html.parser')

            items = soup.select('.item')
            for item in items:
                if len(movies) >= max_movies:
                    break
                rank = item.select_one('.pic em').text
                title = item.select_one('.title').text
                rating = item.select_one('.rating_num').text
                movies.append({
                    'rank': int(rank),
                    'title': title,
                    'rating': float(rating)
                })
                print(f"    {rank}. {title} - {rating}分")

            start += 25
            time.sleep(random.uniform(0.5, 1))

        except Exception as e:
            print(f"    错误: {e}")
            break

    end_time = time.time()
    elapsed = end_time - start_time

    return {
        'name': 'Requests (简化版)',
        'version': '仅列表页',
        'time': elapsed,
        'movie_count': len(movies),
        'avg_time_per_movie': elapsed / len(movies) if movies else 0,
        'success': True
    }


# ==================== 4. 性能对比图表 ====================
def plot_comparison(results):
    """绘制性能对比图"""
    # 过滤成功的测试
    successful = [r for r in results if r.get('success', False)]

    if len(successful) < 2:
        print("\n⚠️ 成功运行的测试不足2个，无法绘制对比图")
        return

    names = [r['name'] for r in successful]
    times = [r['time'] for r in successful]
    avg_times = [r['avg_time_per_movie'] for r in successful]
    counts = [r['movie_count'] for r in successful]

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 颜色
    colors = ['#3498db', '#e74c3c', '#2ecc71']

    # 图1: 总耗时对比
    bars1 = axes[0].bar(names, times, color=colors[:len(names)])
    axes[0].set_ylabel('总耗时 (秒)', fontsize=12)
    axes[0].set_title(f'总耗时对比 (爬取 {counts[0]} 部电影)', fontsize=14)
    axes[0].set_ylim(0, max(times) * 1.2)
    for bar, v in zip(bars1, times):
        axes[0].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                     f'{v:.1f}s', ha='center', fontsize=11)

    # 图2: 平均每部电影耗时对比
    bars2 = axes[1].bar(names, avg_times, color=colors[:len(names)])
    axes[1].set_ylabel('平均耗时 (秒/部)', fontsize=12)
    axes[1].set_title('单部电影平均耗时对比', fontsize=14)
    axes[1].set_ylim(0, max(avg_times) * 1.2)
    for bar, v in zip(bars2, avg_times):
        axes[1].text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.05,
                     f'{v:.3f}s', ha='center', fontsize=11)

    plt.tight_layout()

    # 保存图片
    output_path = os.path.join(PROJECT_ROOT, 'performance_comparison.png')
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"\n📊 性能对比图已保存: {output_path}")

    plt.show()


# ==================== 5. 详细报告 ====================
def print_detailed_report(results):
    """打印详细对比报告"""
    print("\n" + "=" * 70)
    print("📊 性能对比详细报告")
    print("=" * 70)

    # 表格数据
    table_data = []
    for r in results:
        status = "✅ 成功" if r.get('success', False) else "❌ 失败"
        table_data.append({
            '爬虫版本': r['name'],
            '子版本': r.get('version', '-'),
            '状态': status,
            '耗时(秒)': f"{r['time']:.2f}" if r['time'] > 0 else '-',
            '爬取数量': r['movie_count'],
            '平均耗时(秒/部)': f"{r['avg_time_per_movie']:.3f}" if r['avg_time_per_movie'] > 0 else '-'
        })

    df = pd.DataFrame(table_data)
    print(df.to_string(index=False))

    # 成功对比
    successful = [r for r in results if r.get('success', False) and r['time'] > 0 and r['movie_count'] > 0]

    if len(successful) >= 2:
        # 找出两个主要版本
        req_versions = [r for r in successful if 'Requests' in r['name']]
        scrapy_versions = [r for r in successful if 'Scrapy' in r['name']]

        if req_versions and scrapy_versions:
            req = req_versions[0]
            scrapy = scrapy_versions[0]

            if req['time'] > 0 and scrapy['time'] > 0:
                speedup = req['time'] / scrapy['time']

                print("\n" + "=" * 70)
                print("⚡ 性能对比结果")
                print("=" * 70)
                print(f"\n   Requests 版本: {req['time']:.2f} 秒 (爬取 {req['movie_count']} 部)")
                print(f"   Scrapy 版本:   {scrapy['time']:.2f} 秒 (爬取 {scrapy['movie_count']} 部)")
                print(f"\n   🚀 Scrapy 比 Requests 快 {speedup:.2f} 倍")

                # 分析结论
                print("\n" + "=" * 70)
                print("📝 分析结论")
                print("=" * 70)
                print("""
1. Scrapy 框架优势:
   - 内置并发机制，爬取效率更高
   - 自动处理请求去重和限速
   - 模块化设计，易于扩展和维护
   - 内置重试和错误处理机制

2. Requests 版本优势:
   - 代码简单直观，易于理解和调试
   - 依赖少，适合小型项目
   - 灵活性高，可精细控制每个请求

3. 建议:
   - 小规模爬取 (<100页) → Requests 足够
   - 大规模爬取 → Scrapy 更优
   - 生产环境 → Scrapy + 分布式
                """)


# ==================== 6. 主函数 ====================
def main():
    """主函数"""
    print("=" * 70)
    print("🚀 Requests vs Scrapy 性能对比测试")
    print("=" * 70)
    print("\n说明:")
    print("  - 测试爬取 50 部电影（仅列表页）")
    print("  - 对比 requests + BeautifulSoup 和 Scrapy 框架的性能")
    print("  - 结果包括总耗时和平均每部电影耗时")

    # 测试数量
    test_count = 50

    results = []

    print("\n" + "=" * 70)
    print(f"🏁 开始性能测试 (爬取 {test_count} 部电影)")
    print("=" * 70)

    # 1. 运行简化版 Requests
    result1 = run_simple_requests(max_movies=test_count)
    results.append(result1)
    if result1['success']:
        print(f"   ✅ 简化版 Requests 完成: {result1['time']:.2f}秒, {result1['movie_count']}部电影")

    # 2. 运行 Scrapy 版本
    result2 = run_scrapy_version(max_movies=test_count)
    results.append(result2)
    if result2['success']:
        print(f"   ✅ Scrapy 版本完成: {result2['time']:.2f}秒, {result2['movie_count']}部电影")

    # 3. 可选：运行完整版 Requests（需要更多时间）
    print("\n" + "=" * 70)
    print("是否运行完整版 Requests（包含详情页）？")
    print("注意：需要安装 Chrome 浏览器，耗时较长")
    run_full = input("运行完整版？(y/N): ").strip().lower()

    if run_full == 'y':
        result3 = run_requests_version(max_movies=min(test_count, 20))
        results.append(result3)
        if result3['success']:
            print(f"   ✅ 完整版 Requests 完成: {result3['time']:.2f}秒, {result3['movie_count']}部电影")

    # 4. 输出报告
    print_detailed_report(results)

    # 5. 绘制图表
    if len([r for r in results if r.get('success', False) and r['time'] > 0]) >= 2:
        plot_comparison(results)

    print("\n✅ 性能对比测试完成！")


if __name__ == "__main__":
    import random

    main()
