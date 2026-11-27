
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from xml.etree.ElementTree import Element, SubElement, ElementTree
from datetime import datetime, timezone
import re
import html

SITE = "https://www.stnn.cc"
NEWS_URL = "https://www.stnn.cc/news/"
RSS_FILE = "feed.xml"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125 Safari/537.36"
}

def clean_text(text):
    return re.sub(r"\s+", " ", text or "").strip()

def get_page(url):
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print("页面获取失败:", url, e)
        return None

def get_description(url):
    soup = get_page(url)
    if not soup:
        return ""
    for name in ["description"]:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return clean_text(tag["content"])
    tag = soup.find("meta", attrs={"property": "og:description"})
    if tag and tag.get("content"):
        return clean_text(tag["content"])
    return ""

def main():
    soup = get_page(NEWS_URL)
    if not soup:
        raise RuntimeError("新闻列表页面无法获取")

    articles = []
    seen = set()

    for a in soup.find_all("a", href=True):
        title = clean_text(a.get_text())
        url = urljoin(SITE, a["href"])
        parsed = urlparse(url)

        if parsed.netloc not in ("www.stnn.cc", "stnn.cc"):
            continue
        if len(title) < 8 or len(title) > 150:
            continue
        if url.rstrip("/") == NEWS_URL.rstrip("/"):
            continue
        if url in seen:
            continue

        path = parsed.path.lower()
        if any(x in path for x in ["/video/", "/tag/", "/search/", "/author/"]):
            continue
        if path in ["/", "/news", "/news/"]:
            continue

        # 找新闻卡片附近的文本，作为简介候选
        parent = a
        card_text = ""
        for _ in range(4):
            if parent.parent:
                parent = parent.parent
                text = clean_text(parent.get_text(" ", strip=True))
                if len(text) > len(title) + 20:
                    card_text = text
                    break

        description = card_text.replace(title, "", 1).strip()
        description = re.sub(r"\d{4}[-年/]\d{1,2}[-月/]\d{1,2}.*", "", description)
        description = clean_text(description)

        if len(description) < 20:
            description = get_description(url)

        if not description:
            description = title

        seen.add(url)
        articles.append({
            "title": title,
            "url": url,
            "description": description[:800],
        })

        if len(articles) >= 40:
            break

    if not articles:
        raise RuntimeError("未提取到新闻，网站结构可能发生变化")

    rss = Element("rss", version="2.0")
    channel = SubElement(rss, "channel")
    SubElement(channel, "title").text = "星岛环球网新闻 RSS"
    SubElement(channel, "link").text = NEWS_URL
    SubElement(channel, "description").text = "星岛环球网最新新闻自动订阅"
    SubElement(channel, "language").text = "zh-cn"
    SubElement(channel, "lastBuildDate").text = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    for article in articles:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = article["title"]
        SubElement(item, "link").text = article["url"]
        SubElement(item, "guid", isPermaLink="true").text = article["url"]
        SubElement(item, "description").text = article["description"]

    ElementTree(rss).write(RSS_FILE, encoding="utf-8", xml_declaration=True)
    print(f"RSS生成成功，共 {len(articles)} 条新闻")

if __name__ == "__main__":
    main()
