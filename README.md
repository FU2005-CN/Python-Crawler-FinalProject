# 🎬 Python-Crawler-FinalProject: 豆瓣电影 Top250 数据采集与分析系统

> **基于 Python 的全栈数据采集解决方案**
>
> 这是一个完整的数据采集与分析系统，旨在使用 `Scrapy` 框架和 `Selenium` 自动化工具，深度挖掘豆瓣电影 Top250 的详细信息，并进行可视化分析。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue" alt="Python Version">
  <img src="https://img.shields.io/badge/Scrapy-2.11.0-orange" alt="Scrapy Version">
  <img src="https://img.shields.io/badge/Selenium-4.15.0-green" alt="Selenium Version">
  <img src="https://img.shields.io/badge/License-MIT-red" alt="License">
</p>

---

## 📖 项目背景与简介

随着互联网大数据时代的到来，电影评分数据成为了分析大众审美和文化趋势的重要依据。豆瓣电影 Top250 榜单收录了影史上最经典的 250 部电影，具有极高的参考价值。

本项目作为《Python 爬虫技术》课程的期末大作业，不仅实现了基础的数据爬取，更着重解决了**反爬虫对抗**、**动态页面渲染**以及**数据持久化存储**等实际问题。

### ✨ 核心特性
- **动态渲染对抗**：利用 **Selenium** 模拟真实浏览器行为，绕过豆瓣的 JavaScript 加密和动态加载机制。
- **智能反爬策略**：
    - 随机 User-Agent 池。
    - 动态 Cookie 自动维护。
    - 请求失败自动重试机制（Retry Middleware）。
- **多维度数据存储**：支持将清洗后的数据导出为 **CSV** 文件，或直接写入 **MySQL** 数据库。
- **可视化分析**：提供数据分析脚本，生成评分分布图、词云图等可视化报表。

---

## 🛠️ 技术架构

本项目采用了经典的爬虫技术栈，结合了同步与异步请求的优势。

- **核心语言**: Python 3.9+
- **爬虫框架**: Scrapy (用于调度与管道管理)
- **浏览器自动化**: Selenium 4 + Chrome WebDriver
- **解析库**: BeautifulSoup4 (lxml 解析器), re (正则表达式)
- **数据处理**: Pandas, Jieba (中文分词)
- **数据库**: MySQL 8.0 / SQLite
- **可视化**: Matplotlib, WordCloud

---

## 📂 项目目录结构

```text
Python-Crawler-FinalProject/
├── daima/                      # 核心代码目录
│   ├── douban_spider.py        # 主爬虫脚本 (Selenium + Requests 混合版)
│   ├── performance_compare.py  # 性能对比测试脚本
│   └── qingan/                 # (包含情感分析或其他模块)
├── data/                       # 数据存储目录 (CSV/JSON)
├── images/                     # 可视化结果图片
├── .gitignore                  # Git 忽略配置
├── LICENSE                     # 开源协议
├── requirements.txt            # 依赖库列表
└── README.md                   # 项目说明文档
