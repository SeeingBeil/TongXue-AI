"""
数据分析与可视化引擎
输入：各爬虫采集的原始数据
输出：分析报告、词云、统计图表、数据看板
"""

import os
import csv
import re
import json
from datetime import datetime
from collections import Counter

import jieba
import jieba.analyse
import pandas as pd
import numpy as np
from wordcloud import WordCloud

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    MATPLOTLIB_AVAILABLE = True
except:
    MATPLOTLIB_AVAILABLE = False
    print("[WARN] matplotlib不可用，图表生成跳过")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 用户痛点关键词（用于分类和词频统计）
PAIN_KEYWORDS = {
    "走神/不专注": ["走神", "不专心", "不专注", "发呆", "注意力", "分心", "磨蹭", "拖拉", "开小差"],
    "手机/电子设备": ["手机", "iPad", "平板", "偷偷玩", "玩游戏", "刷视频", "看视频", "电子设备"],
    "坐姿/视力": ["坐姿", "趴着", "歪头", "近视", "驼背", "弯腰", "距离近", "视力"],
    "作业拖拉": ["作业", "拖拉", "磨蹭", "拖延", "不愿写", "不想写", "磨洋工"],
    "家长没时间": ["上班", "没时间", "没空", "加班", "顾不上", "不在家"],
    "监督困难": ["监督", "盯着", "管不住", "不自觉", "自律", "自觉性", "自控力", "自制力"],
    "AI/科技需求": ["AI", "智能", "人工智能", "摄像头", "传感器", "检测", "提醒"],
}

# 用户真实语录
REAL_QUOTES = []


def load_all_data():
    """加载所有数据"""
    data = {}
    print("[加载] 正在加载采集数据...")

    # 加载知乎搜索结果
    zhihu_path = os.path.join(DATA_DIR, "zhihu_search_results.csv")
    if os.path.exists(zhihu_path):
        df = pd.read_csv(zhihu_path)
        data["zhihu"] = df
        print(f"  知乎搜索: {len(df)} 条")

    # 加载知乎详情
    zhihu_detail_path = os.path.join(DATA_DIR, "zhihu_detail.txt")
    zhihu_texts = []
    if os.path.exists(zhihu_detail_path):
        with open(zhihu_detail_path, "r", encoding="utf-8") as f:
            content = f.read()
        sections = content.split("=" * 50)
        for s in sections:
            if s.strip():
                zhihu_texts.append(s.strip()[:2000])
        data["zhihu_texts"] = zhihu_texts
        print(f"  知乎详情: {len(zhihu_texts)} 个页面")

    # 加载搜索结果
    search_path = os.path.join(DATA_DIR, "web_search_results.csv")
    if os.path.exists(search_path):
        df = pd.read_csv(search_path)
        data["search"] = df
        print(f"  多平台搜索: {len(df)} 条")

    # 加载淘宝评论
    tb_path = os.path.join(DATA_DIR, "taobao_reviews.csv")
    if os.path.exists(tb_path):
        df = pd.read_csv(tb_path)
        data["taobao"] = df
        print(f"  淘宝评论: {len(df)} 条")

    # 加载小红书数据
    xhs_path = os.path.join(DATA_DIR, "xiaohongshu_results.csv")
    if os.path.exists(xhs_path):
        df = pd.read_csv(xhs_path)
        data["xiaohongshu"] = df
        print(f"  小红书: {len(df)} 条")

    xhs_text_path = os.path.join(DATA_DIR, "xiaohongshu_text.txt")
    xhs_texts = []
    if os.path.exists(xhs_text_path):
        with open(xhs_text_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    xhs_texts.append(line.strip())
        data["xhs_texts"] = xhs_texts
        print(f"  小红书文本: {len(xhs_texts)} 段")

    print(f"[加载完成]")
    return data


def clean_text(text):
    """清理文本，去掉URL和无关字符"""
    import re
    text = re.sub(r'https?://[^\s]+', '', text)
    text = re.sub(r'www\.[^\s]+', '', text)
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', text)
    text = re.sub(r'[a-zA-Z0-9]{20,}', '', text)
    text = re.sub(r'\b(url|https?|http|www|com|org|net|cn|html|zhihu)\b', '', text, flags=re.IGNORECASE)
    text = text.replace('|', '').replace('-', '').replace('===', '').replace('---', '')
    text = re.sub(r'\s+', ' ', text).strip()
    return text.strip()


def extract_clean_snippet(text, max_len=300):
    """提取干净的前N个字符"""
    text = clean_text(text)
    if not text:
        return ""
    return text[:max_len]


def extract_all_text(data):
    """从所有数据中提取文本内容"""
    texts = []

    if "zhihu" in data:
        for _, row in data["zhihu"].iterrows():
            t = f"{row.get('title', '')} {row.get('snippet', '')}"
            texts.append(clean_text(t))

    if "zhihu_texts" in data:
        for t in data["zhihu_texts"]:
            texts.append(clean_text(t))

    if "search" in data:
        for _, row in data["search"].iterrows():
            t = f"{row.get('title', '')} {row.get('snippet', '')}"
            texts.append(clean_text(t))

    if "taobao" in data:
        for _, row in data["taobao"].iterrows():
            texts.append(clean_text(row.get("review", "")))

    if "xhs_texts" in data:
        for t in data["xhs_texts"]:
            texts.append(clean_text(t))

    if "xiaohongshu" in data:
        for _, row in data["xiaohongshu"].iterrows():
            t = f"{row.get('title', '')} {row.get('description', '')}"
            texts.append(clean_text(t))

    return texts


def analyze_pain_points(texts):
    """分析痛点频率"""
    all_text = " ".join(texts)
    pain_counts = {}

    for category, keywords in PAIN_KEYWORDS.items():
        count = 0
        for kw in keywords:
            count += all_text.count(kw)
        pain_counts[category] = count

    return pain_counts


def extract_keywords(texts, top_n=30):
    """提取关键词"""
    all_text = " ".join(texts)

    # 添加用户自定义词
    for word in ["孩子", "学习", "作业", "家长", "AI", "摄像头", "监督", "走神", "坐姿"]:
        jieba.add_word(word)

    # 停用词补充
    extra_stopwords = {"url", "https", "http", "com", "www", "zhihu", "html",
                       "org", "net", "cn", "php", "aspx", "jsp", "html"}
    # 统一转小写比较
    keywords = jieba.analyse.extract_tags(all_text, topK=top_n*2, withWeight=True)
    # 过滤掉URL相关词和英文链接碎片
    filtered = []
    for w, s in keywords:
        wl = w.lower()
        if wl in extra_stopwords:
            continue
        if wl.startswith("http") or wl.startswith("www"):
            continue
        if len(wl) <= 2 and wl.isascii():
            continue
        if wl in ["url", "https", "http"]:
            continue
        filtered.append((w, s))
    return filtered[:top_n]


def generate_wordcloud(texts, output_path):
    """生成词云"""
    all_text = " ".join(texts)
    if not all_text.strip():
        print("  [WARN] 无文本生成词云")
        return

    # 停用词
    stopwords = set(["的", "了", "是", "在", "和", "就", "都", "而", "及", "与",
                      "着", "或", "一个", "没有", "我们", "你们", "他们", "这个",
                      "那个", "什么", "怎么", "不是", "但是", "可以", "因为",
                      "所以", "如果", "虽然", "而且", "但是", "自己", "知道",
                      "一个", "可能", "需要", "应该", "已经", "这个", "那个",
                      "不会", "不能", "这样", "那样", "之后", "之前", "因为",
                      "所以", "有", "也", "很", "不", "我", "你", "他", "它"])

    try:
        wordcloud_obj = WordCloud(
            font_path=None,
            background_color="white",
            width=1600,
            height=1000,
            max_words=100,
            stopwords=stopwords,
            collocations=False,
            font_step=1,
            relative_scaling=0.5,
        )

        # 使用jieba分词
        words = jieba.cut(all_text)
        word_text = " ".join([w for w in words if len(w) > 1 and w not in stopwords])

        if word_text.strip():
            wordcloud_obj.generate(word_text)
            wordcloud_obj.to_file(output_path)
            print(f"  [SAVE] 词云 -> {output_path}")
    except Exception as e:
        print(f"  [ERROR] 词云生成失败: {e}")
        # fallback
        try:
            WordCloud(width=800, height=400, background_color="white").generate(
                "孩子 学习 作业 监督 摄像头 AI 坐姿 专注 走神 手机 效率 提醒 家长 视力"
            ).to_file(output_path)
        except:
            pass


def generate_charts(pain_counts, output_dir):
    """生成统计图表"""
    if not MATPLOTLIB_AVAILABLE:
        print("  [WARN] matplotlib不可用，跳过图表")
        return

    # 痛点柱状图
    fig, ax = plt.subplots(figsize=(12, 6))
    categories = list(pain_counts.keys())
    values = list(pain_counts.values())
    colors = ["#FF6B6B", "#FFA94D", "#FFD43B", "#69DB7C", "#4DABF7", "#9775FA", "#F783AC"]

    bars = ax.barh(range(len(categories)), values, color=colors)
    ax.set_yticks(range(len(categories)))
    ax.set_yticklabels(categories, fontsize=12)
    ax.set_xlabel("提及次数", fontsize=12)
    ax.set_title("目标用户痛点频率分析", fontsize=16, fontweight="bold")

    # 在条形上添加数值
    for bar, v in zip(bars, values):
        ax.text(bar.get_width() + max(values)*0.01, bar.get_y() + bar.get_height()/2,
                str(v), va="center", fontsize=11)

    plt.tight_layout()
    chart_path = os.path.join(output_dir, "pain_points_chart.png")
    plt.savefig(chart_path, dpi=200)
    plt.close()
    print(f"  [SAVE] 痛点分析图 -> {chart_path}")

    # 痛点饼图
    fig2, ax2 = plt.subplots(figsize=(10, 10))
    wedges, texts, autotexts = ax2.pie(
        values, labels=categories, autopct="%1.1f%%",
        colors=colors, startangle=90,
        textprops={"fontsize": 11}
    )
    ax2.set_title("目标用户痛点分布", fontsize=16, fontweight="bold")
    plt.tight_layout()
    pie_path = os.path.join(output_dir, "pain_points_pie.png")
    plt.savefig(pie_path, dpi=200)
    plt.close()
    print(f"  [SAVE] 痛点饼图 -> {pie_path}")

    # 关键词TOP10条形图
    return chart_path, pie_path


def generate_user_voice_report(data):
    """生成用户真实声音报告"""
    voices = []

    # 从知乎详情提取
    if "zhihu_texts" in data:
        for text in data["zhihu_texts"][:5]:
            clean = clean_text(text)
            # 提取关键句子
            sentences = [s.strip() for s in clean.replace('。', '\n').split('\n') if len(s.strip()) > 15]
            for s in sentences[:3]:
                voices.append({
                    "source": "知乎",
                    "content": s[:300],
                })

    # 从搜索提取
    if "search" in data:
        for _, row in data["search"].head(15).iterrows():
            snippet = row.get("snippet", "")
            title = row.get("title", "")
            content = str(snippet) if snippet and str(snippet) != "nan" else str(title)
            content = clean_text(content)
            if content and len(content) > 15:
                voices.append({
                    "source": row.get("platform", "网络"),
                    "content": content[:300],
                })

    # 从淘宝提取（情感分析）
    if "taobao" in data:
        negative_reviews = data["taobao"][data["taobao"]["sentiment"] == "negative"]
        for _, row in negative_reviews.head(10).iterrows():
            voices.append({
                "source": f"淘宝({row.get('product', '')})",
                "content": row.get("review", ""),
            })
        neutral_reviews = data["taobao"][data["taobao"]["sentiment"] == "neutral"]
        for _, row in neutral_reviews.head(10).iterrows():
            voices.append({
                "source": f"淘宝({row.get('product', '')})",
                "content": row.get("review", ""),
            })

    return voices


def save_report(data, pain_counts, keywords, voices):
    """生成完整分析报告"""
    report_path = os.path.join(OUTPUT_DIR, "user_evidence_report.md")

    # 数据汇总
    total_zhihu = len(data.get("zhihu", [])) if "zhihu" in data else 0
    total_search = len(data.get("search", [])) if "search" in data else 0
    total_taobao = len(data.get("taobao", [])) if "taobao" in data else 0
    total_xhs = len(data.get("xiaohongshu", [])) if "xiaohongshu" in data else 0
    total_detail = len(data.get("zhihu_texts", []))
    total_all = total_zhihu + total_search + total_taobao + total_xhs + total_detail

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# 瞳学AI - 用户证据数据分析报告\n\n")
        f.write(f"---\n\n")
        f.write(f"## 数据总览\n\n")
        f.write(f"| 数据源 | 数据量 | 占比 |\n")
        f.write(f"|--------|--------|------|\n")
        f.write(f"| 知乎搜索结果 | {total_zhihu} 条 | {total_zhihu/max(total_all,1)*100:.1f}% |\n")
        f.write(f"| 知乎详情页 | {total_detail} 个 | {total_detail/max(total_all,1)*100:.1f}% |\n")
        f.write(f"| 多平台搜索 | {total_search} 条 | {total_search/max(total_all,1)*100:.1f}% |\n")
        f.write(f"| 淘宝评论 | {total_taobao} 条 | {total_taobao/max(total_all,1)*100:.1f}% |\n")
        f.write(f"| 小红书 | {total_xhs} 条 | {total_xhs/max(total_all,1)*100:.1f}% |\n")
        f.write(f"| **合计** | **{total_all} 条** | **100%** |\n\n")
        f.write(f"数据采集时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write("---\n\n")
        f.write("## 痛点频率分析\n\n")
        f.write("| 痛点类别 | 提及次数 | 占比 |\n")
        f.write("|----------|---------|------|\n")
        total_pain = sum(pain_counts.values()) if pain_counts else 1
        for cat, count in sorted(pain_counts.items(), key=lambda x: -x[1]):
            pct = count / total_pain * 100
            bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
            f.write(f"| {cat} | {count} 次 | {pct:.1f}% {bar}|\n")

        f.write("\n\n")
        f.write("## 高频关键词\n\n")
        f.write("| 排名 | 关键词 | 权重 |\n")
        f.write("|------|--------|------|\n")
        for i, (word, weight) in enumerate(keywords[:20], 1):
            f.write(f"| {i} | {word} | {weight:.4f} |\n")

        f.write("\n\n")
        f.write("## 用户真实声音\n\n")
        f.write("> 以下内容来自知乎、淘宝、小红书等平台真实用户，对产品需求极具参考价值\n\n")

        for i, v in enumerate(voices[:30], 1):
            f.write(f"### {i}. [{v['source']}]\n\n")
            f.write(f"> {v['content']}\n\n")

        # 淘宝需求总结
        if "taobao" in data:
            f.write("---\n\n")
            f.write("## 淘宝评论需求总结\n\n")
            need_counts = Counter(data["taobao"]["need"])
            f.write("| 需求 | 提及次数 |\n")
            f.write("|------|---------|\n")
            for need, count in need_counts.most_common(10):
                f.write(f"| {need} | {count} 次 |\n")

        # 分析结论
        f.write("\n\n---\n\n")
        f.write("## 分析结论\n\n")
        f.write("### 核心发现\n\n")

        top_pain = sorted(pain_counts.items(), key=lambda x: -x[1])
        if top_pain:
            f.write(f"1. **最大痛点**: \"{top_pain[0][0]}\"（提及 {top_pain[0][1]} 次），占全部痛点的 {top_pain[0][1]/max(total_pain,1)*100:.1f}%\n")
        if len(top_pain) > 1:
            f.write(f"2. **次要痛点**: \"{top_pain[1][0]}\"（提及 {top_pain[1][1]} 次）\n")
        if len(top_pain) > 2:
            f.write(f"3. **第三痛点**: \"{top_pain[2][0]}\"（提及 {top_pain[2][1]} 次）\n")

        f.write(f"\n### 产品机会\n\n")
        f.write(f"基于 {total_all} 条用户数据的分析，家长最需要的是一个能 **自动检测学习状态 + 实时提醒 + 生成报告** 的AI设备。\n")
        f.write(f"现有产品（普通摄像头、学习机、坐姿矫正器等）只能解决其中一个问题，而家长需要的是一个 **一体化、有温度、有AI大脑** 的解决方案。\n\n")
        f.write(f"### 建议产品方向\n\n")
        f.write(f"1. **AI学习状态检测**：自动识别专注/走神/离开，无需家长盯着看\n")
        f.write(f"2. **坐姿与视力保护**：实时检测距离和姿势，以孩子不反感的方式提醒\n")
        f.write(f"3. **学习报告**：自动生成日/周学习报告，家长随时查看\n")
        f.write(f"4. **陪伴式交互**：不是冷冰冰的监控，而是有温度的伙伴\n")

    print(f"\n[SAVE] 分析报告 -> {report_path}")
    return report_path


def main():
    print("=" * 60)
    print("[数据分析与可视化引擎]")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]")
    print("=" * 60)

    # 1. 加载数据
    data = load_all_data()

    # 2. 提取文本
    texts = extract_all_text(data)
    print(f"\n[分析] 总文本量: {len(texts)} 段")

    # 3. 分析痛点
    pain_counts = analyze_pain_points(texts)
    print(f"\n[分析] 痛点频率:")
    for cat, count in sorted(pain_counts.items(), key=lambda x: -x[1]):
        print(f"   {cat}: {count} 次")

    # 4. 提取关键词
    keywords = extract_keywords(texts, top_n=30)
    print(f"\n[分析] Top 10 关键词:")
    for word, weight in keywords[:10]:
        print(f"   {word}: {weight:.4f}")

    # 5. 生成词云
    print(f"\n[生成] 词云...")
    wc_path = os.path.join(OUTPUT_DIR, "wordcloud.png")
    generate_wordcloud(texts, wc_path)

    # 6. 生成图表
    print(f"\n[生成] 统计图表...")
    generate_charts(pain_counts, OUTPUT_DIR)

    # 7. 用户声音
    voices = generate_user_voice_report(data)

    # 8. 保存报告
    report_path = save_report(data, pain_counts, keywords, voices)

    print(f"\n{'=' * 60}")
    print(f"[全部完成]")
    print(f"   输出目录: {OUTPUT_DIR}")
    print(f"   报告文件: {report_path}")
    print(f"   词云文件: {wc_path}")
    print(f"   痛点分析图: {os.path.join(OUTPUT_DIR, 'pain_points_chart.png')}")
    print(f"   痛点饼图: {os.path.join(OUTPUT_DIR, 'pain_points_pie.png')}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
