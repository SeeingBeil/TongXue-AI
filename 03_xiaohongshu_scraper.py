"""
小红书数据采集器 - 使用 Selenium 自动化浏览器
目标：搜索"孩子学习监督""AI学习"等关键词，采集帖子和评论
注意：需要安装Chrome浏览器，selenium会自动管理chromedriver
"""

import os
import csv
import json
import time
import random
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

SEARCH_KEYWORDS = [
    "孩子学习监督",
    "儿童学习摄像头",
    "孩子写作业坐姿",
    "AI学习助手",
    "儿童专注力",
    "学习自律",
]

# 小红书搜索URL模板
SEARCH_URL_TEMPLATE = "https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"


def create_driver():
    """创建Chrome浏览器实例"""
    options = Options()
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    # 不开启headless模式，因为小红书有反爬，需要能看到页面
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    # 使用已安装的Chrome
    options.binary_location = "C:/Program Files/Google/Chrome/Application/chrome.exe"

    driver = webdriver.Chrome(options=options)
    # 隐藏webdriver特征
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5]
        });
        """
    })
    return driver


def scrape_xiaohongshu(keyword, max_notes=20):
    """搜索小红书并采集帖子信息"""
    driver = create_driver()
    results = []

    try:
        encoded_keyword = keyword.replace(" ", "%20")
        search_url = SEARCH_URL_TEMPLATE.format(keyword=encoded_keyword)
        print(f"\n[搜索] 正在搜索: {keyword}")
        print(f"   URL: {search_url}")
        driver.get(search_url)

        # 等待搜索结果加载
        print(f"   等待页面加载...")
        time.sleep(5)

        # 滚动页面以加载更多
        for scroll in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            print(f"   滚动 {scroll+1}/3...")
            time.sleep(random.uniform(2, 4))

        # 提取页面中可见的笔记信息
        print(f"   尝试提取笔记信息...")

        # 尝试多种选择器来匹配小红书页面结构
        selectors = [
            "section.note-item",
            "div.note-item",
            "div.feeds-page div.note-item",
            "a[href*='/explore/']",
            "a[href*='/discovery/item/']",
            "div[class*='note']",
            "li[class*='note']",
            "div[class*='card']",
        ]

        notes_found = []
        for selector in selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
            if elements:
                print(f"   选择器 '{selector}' 找到 {len(elements)} 个元素")
                notes_found = elements[:max_notes]
                break

        # 提取页面文本内容作为搜索结果
        if not notes_found:
            print(f"   使用页面文本提取方式...")
            body_text = driver.find_element(By.TAG_NAME, "body").text
            # 保存页面源码供分析
            page_source_path = os.path.join(OUTPUT_DIR, f"xhs_page_{keyword}.html")
            with open(page_source_path, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print(f"   页面源码已保存到 {page_source_path}")

            # 从页面文本中提取与关键词相关的段落
            lines = body_text.split("\n")
            relevant_lines = [l.strip() for l in lines if len(l.strip()) > 10 and any(
                kw in l for kw in ["孩子", "学习", "作业", "坐姿", "专注", "监督", "摄像头", "AI"]
            )]

            for line in relevant_lines[:max_notes]:
                results.append({
                    "keyword": keyword,
                    "content": line[:300],
                    "source": "xiaohongshu_page_text",
                })

            print(f"   从页面文本提取 {len(results)} 条相关内容")

        else:
            for note in notes_found:
                try:
                    title_el = note.find_element(By.CSS_SELECTOR, "h3, .title, a")
                    title = title_el.text.strip() or title_el.get_attribute("title") or ""
                    link = title_el.get_attribute("href") or ""

                    desc_el = note.find_element(By.CSS_SELECTOR, ".desc, .content, p")
                    desc = desc_el.text.strip() if desc_el else ""

                    results.append({
                        "keyword": keyword,
                        "title": title[:200],
                        "description": desc[:500],
                        "url": link,
                        "source": "xiaohongshu",
                    })
                except:
                    pass

            print(f"   提取到 {len(results)} 条笔记")

    except Exception as e:
        print(f"   [ERROR] 小红书采集失败: {e}")

    finally:
        driver.quit()

    return results


def save_results(all_results):
    """保存所有结果"""
    if not all_results:
        print("[WARN] 无数据可保存")
        return

    csv_path = os.path.join(OUTPUT_DIR, "xiaohongshu_results.csv")
    fields = ["keyword", "title", "description", "url", "source", "content"]

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in all_results:
            row = {k: r.get(k, "") for k in fields}
            writer.writerow(row)

    print(f"\n[SAVE] {len(all_results)} 条 -> {csv_path}")

    # 也保存纯文本用于分析
    txt_path = os.path.join(OUTPUT_DIR, "xiaohongshu_text.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for r in all_results:
            content = r.get("title", "") + " " + r.get("description", "") + " " + r.get("content", "")
            if content.strip():
                f.write(content.strip() + "\n")
    print(f"[SAVE] 文本 -> {txt_path}")


def main():
    print("=" * 60)
    print("[小红书数据采集器]")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print("=" * 60)

    all_results = []

    for kw in SEARCH_KEYWORDS:
        try:
            results = scrape_xiaohongshu(kw, max_notes=15)
            all_results.extend(results)
        except Exception as e:
            print(f"  [ERROR] 关键词 '{kw}' 处理失败: {e}")

        # 关键词间间隔
        time.sleep(random.uniform(3, 6))

    save_results(all_results)
    print(f"\n[完成] 总计采集 {len(all_results)} 条")


if __name__ == "__main__":
    main()
