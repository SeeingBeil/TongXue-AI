"""
知乎数据采集器 v2 - 使用zhuanlan/网页搜索采集
替代方案：通过搜索引擎抓取知乎内容 + 直接访问知乎问题页
不需要Cookie
"""

import requests
import csv
import re
import time
import random
import os
from urllib.parse import quote
from datetime import datetime
from bs4 import BeautifulSoup

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 搜索关键词（知乎相关问题）
ZHIHU_SEARCH_QUERIES = [
    "site:zhihu.com 孩子学习 不专心",
    "site:zhihu.com 监督 孩子 写作业",
    "site:zhihu.com 孩子 学习 摄像头",
    "site:zhihu.com 儿童 坐姿 矫正",
    "site:zhihu.com 孩子 走神 专注力",
    "site:zhihu.com AI 学习 监督 儿童",
    "site:zhihu.com 孩子 作业 拖拉 怎么办",
    "site:zhihu.com 家用摄像头 孩子 学习",
    "site:zhihu.com 小学生 学习 效率 低",
    "site:zhihu.com 防近视 儿童 设备",
]


def search_zhihu_content(query):
    """通过搜索引擎抓取知乎内容"""
    url = f"https://www.bing.com/search?q={quote(query)}&count=30"
    results = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return results

        soup = BeautifulSoup(resp.text, "html.parser")
        items = soup.find_all("li", class_="b_algo")

        for item in items:
            link_el = item.find("a")
            if not link_el:
                continue
            href = link_el.get("href", "")
            if "zhihu.com" not in href:
                continue

            title = link_el.get_text(strip=True)
            snippet_el = item.find("p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            results.append({
                "title": title,
                "url": href,
                "snippet": snippet[:500],
                "search_query": query,
            })

    except Exception as e:
        print(f"  [ERROR] 搜索失败: {e}")

    return results


def scrape_zhihu_question_page(url):
    """直接访问知乎问题页，提取问题和部分回答摘要"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # 提取问题标题
        title_el = soup.find("h1", class_="QuestionHeader-title")
        title = title_el.get_text(strip=True) if title_el else ""

        # 提取问题描述
        desc_el = soup.find("div", class_="QuestionHeader-detail")
        description = desc_el.get_text(strip=True) if desc_el else ""

        # 提取回答摘要（知乎页面通常会预渲染一些回答）
        answer_items = soup.find_all("div", class_="AnswerItem")
        answers = []
        for item in answer_items[:10]:
            content_el = item.find("div", class_="RichContent-inner")
            if content_el:
                answers.append(content_el.get_text(strip=True)[:1000])

        return {
            "url": url,
            "title": title,
            "description": description[:500],
            "answers": answers,
        }
    except Exception as e:
        print(f"  [ERROR] 访问 {url[:50]}... 失败: {e}")
        return None


def main():
    print("=" * 60)
    print("[知乎数据采集器 v2]")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print("=" * 60)

    # 第一步：通过搜索引擎找知乎内容
    print("\n[Step 1] 搜索知乎内容...")
    all_entries = []
    seen_urls = set()

    for query in ZHIHU_SEARCH_QUERIES:
        print(f"   搜索: {query[:40]}...")
        results = search_zhihu_content(query)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_entries.append(r)
        print(f"   -> 发现 {len(results)} 条，累计 {len(all_entries)} 条")
        time.sleep(random.uniform(1.5, 3.0))

    # 第二步：尝试直接访问知乎问题页提取更详细内容
    print(f"\n[Step 2] 访问知乎问题页提取详细内容...")
    detailed_pages = []
    for entry in all_entries[:20]:  # 取前20个
        print(f"   访问: {entry['title'][:40]}...")
        page_data = scrape_zhihu_question_page(entry["url"])
        if page_data:
            detailed_pages.append(page_data)
        time.sleep(random.uniform(2, 4))

    # 第三步：保存搜索结果
    if all_entries:
        csv_path = os.path.join(OUTPUT_DIR, "zhihu_search_results.csv")
        fields = ["title", "url", "snippet", "search_query"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in all_entries:
                writer.writerow({k: r.get(k, "") for k in fields})
        print(f"\n[SAVE] {len(all_entries)} 条搜索结果 -> {csv_path}")

    # 第四步：保存详细页面内容
    if detailed_pages:
        txt_path = os.path.join(OUTPUT_DIR, "zhihu_detail.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            for page in detailed_pages:
                f.write(f"=== {page['title']} ===\n")
                f.write(f"URL: {page['url']}\n")
                f.write(f"描述: {page['description']}\n\n")
                f.write("回答摘要:\n")
                for i, ans in enumerate(page["answers"], 1):
                    f.write(f"  --- 回答{i} ---\n")
                    f.write(f"  {ans}\n\n")
                f.write("=" * 50 + "\n\n")
        print(f"[SAVE] {len(detailed_pages)} 个页面 -> {txt_path}")

    print(f"\n[完成] 总计搜索到 {len(all_entries)} 条知乎内容，详细采集 {len(detailed_pages)} 个页面")
    return all_entries, detailed_pages


if __name__ == "__main__":
    main()
