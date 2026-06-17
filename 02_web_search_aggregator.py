"""
Web搜索聚合器 - 通过搜索引擎采集各平台公开数据
目标：采集小红书/抖音/微博/百度贴吧等平台关于"孩子学习监督"的公开讨论
"""

import requests
import csv
import time
import random
import os
import re
from urllib.parse import quote
from datetime import datetime
from collections import Counter

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

KEYWORDS = [
    "孩子学习不专心怎么办",
    "在家监督孩子写作业",
    "儿童学习摄像头推荐",
    "孩子写作业走神",
    "学习监督神器",
    "AI学习监督",
    "儿童坐姿矫正",
    "孩子写作业坐姿",
    "防近视学习设备",
    "孩子在家学习效率低",
    "学生专注力训练",
    "儿童学习桌椅",
    "学生监督摄像头",
    "智能学习助手",
    "家里装摄像头看孩子学习",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def search_bing(keyword):
    """用Bing搜索各平台内容"""
    encoded = quote(f"{keyword}")
    url = f"https://www.bing.com/search?q={encoded}&count=30"
    results = []

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return results

        html = resp.text
        # 提取搜索结果中的标题和摘要
        # Bing搜索结果在 <li class="b_algo"> 中
        items = re.findall(r'<li class="b_algo"[^>]*>(.*?)</li>', html, re.DOTALL)

        for item in items:
            title_match = re.search(r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>', item, re.DOTALL)
            snippet_match = re.search(r'<p[^>]*>(.*?)</p>', item, re.DOTALL)

            if title_match:
                url = title_match.group(1)
                title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""

                # 过滤出目标平台
                if any(domain in url for domain in [
                    "xiaohongshu.com", "douyin.com", "weibo.com",
                    "baidu.com", "zhihu.com", "bilibili.com",
                    "reddit.com", "quora.com", "163.com",
                    "sohu.com", "sina.com", "qq.com"
                ]):
                    results.append({
                        "keyword": keyword,
                        "platform": extract_platform(url),
                        "url": url,
                        "title": title,
                        "snippet": snippet,
                        "source": "bing",
                    })

        # 也尝试从常规搜索结果中提取
        if not items:
            # fallback: 提取所有链接
            all_links = re.findall(r'<a[^>]*href="(https?://[^"]+)"[^>]*>', html)
            for url in all_links:
                if any(domain in url for domain in ["xiaohongshu.com", "douyin.com", "weibo.com",
                                                      "zhihu.com", "bilibili.com", "reddit.com"]):
                    if url not in [r["url"] for r in results]:
                        results.append({
                            "keyword": keyword,
                            "platform": extract_platform(url),
                            "url": url,
                            "title": url[:100],
                            "snippet": "",
                            "source": "bing_fallback",
                        })

    except Exception as e:
        print(f"  [ERROR] Bing搜索失败: {e}")

    return results


def extract_platform(url):
    """从URL中提取平台名"""
    if "xiaohongshu" in url:
        return "小红书"
    elif "douyin" in url or "iesdouyin" in url:
        return "抖音"
    elif "weibo" in url:
        return "微博"
    elif "zhihu" in url:
        return "知乎"
    elif "bilibili" in url or "b23" in url:
        return "B站"
    elif "tieba" in url or "baidu" in url:
        return "百度贴吧/百家号"
    elif "reddit" in url:
        return "Reddit"
    elif "quora" in url:
        return "Quora"
    elif "163" in url:
        return "网易"
    elif "sohu" in url:
        return "搜狐"
    elif "sina" in url:
        return "新浪"
    elif "qq" in url:
        return "腾讯"
    else:
        return "其他"


def main():
    print("=" * 60)
    print("[多平台搜索聚合器]")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print(f"关键词数: {len(KEYWORDS)}")
    print("=" * 60)

    all_results = []

    for i, kw in enumerate(KEYWORDS):
        print(f"\n[{i+1}/{len(KEYWORDS)}] 搜索: {kw}")
        bing_results = search_bing(kw)
        all_results.extend(bing_results)
        print(f"   Bing -> {len(bing_results)} 条")
        time.sleep(random.uniform(1.0, 2.0))

    # 去重
    seen = set()
    unique_results = []
    for r in all_results:
        key = r.get("url", r.get("title", ""))
        if key not in seen:
            seen.add(key)
            unique_results.append(r)

    # 保存
    if unique_results:
        csv_path = os.path.join(OUTPUT_DIR, "web_search_results.csv")
        fields = ["keyword", "platform", "url", "title", "snippet", "source"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in unique_results:
                writer.writerow({k: r.get(k, "") for k in fields})
        print(f"\n[完成] 总计 {len(unique_results)} 条结果 (去重后) -> {csv_path}")

        # 统计
        platform_count = Counter(r["platform"] for r in unique_results)
        print("\n平台分布：")
        for p, c in platform_count.most_common():
            print(f"   {p}: {c} 条")
    else:
        print("\n[完成] 未采集到数据")


if __name__ == "__main__":
    main()
