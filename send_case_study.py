import os
import json
import random
import re
import requests
from datetime import datetime
from xml.etree import ElementTree
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

SOURCES = [
    {
        "name": "Harvard Business Review",
        "url": "http://feeds.harvardbusiness.org/harvardbusiness",
        "type": "rss",
    },
    {
        "name": "MIT Sloan School of Management",
        "url": "https://news.mit.edu/rss/school/management",
        "type": "rss",
    },
    {
        "name": "Knowledge@Wharton",
        "url": "https://knowledge.wharton.upenn.edu/feed/",
        "type": "rss",
    },
    {
        "name": "Kellogg Insight",
        "url": "https://insight.kellogg.northwestern.edu/feed",
        "type": "rss",
    },
    {
        "name": "Stanford GSB Insights",
        "url": "https://www.gsb.stanford.edu/insights",
        "type": "html",
    },
]

FALLBACK = {
    "title": "The Case for Good Jobs",
    "link": "https://hbr.org/2023/11/the-case-for-good-jobs",
    "description": "How great companies bring dignity, pay, and meaning to every employee.",
}


def fetch_rss(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        ctype = resp.headers.get("content-type", "")
        if "json" in ctype:
            data = resp.json()
            articles = []
            for item in data.get("items", []):
                title = item.get("title", "").strip()
                link = item.get("url", item.get("external_url", "")).strip()
                raw = item.get("summary") or item.get("content_text") or ""
                desc = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True) if raw else ""
                if title and link:
                    articles.append({"title": title, "link": link, "description": desc})
            return articles
        root = ElementTree.fromstring(resp.content)
        articles = []
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            desc = BeautifulSoup(item.findtext("description", "") or "", "html.parser").get_text(separator=" ", strip=True)
            if title and link:
                articles.append({"title": title, "link": link, "description": desc})
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.iter(f"{{{atom_ns}}}entry"):
            title = entry.findtext(f"{{{atom_ns}}}title", "").strip()
            link_el = entry.find(f"{{{atom_ns}}}link")
            link = link_el.get("href", "").strip() if link_el is not None else ""
            desc = entry.findtext(f"{{{atom_ns}}}summary", "")
            if desc:
                desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
            if title and link:
                articles.append({"title": title, "link": link, "description": desc})
        return articles
    except Exception as e:
        print(f"RSS fail {url}: {e}")
        return []


def fetch_html_articles(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        articles = []
        seen = set()
        for tag in soup.select("a[href]"):
            href = tag.get("href", "")
            text = tag.get_text(strip=True)
            if not text or len(text) < 20:
                continue
            if not href.startswith("http"):
                href = requests.compat.urljoin(url, href)
            if href in seen:
                continue
            seen.add(href)
            parent = tag.find_parent(["article", "div", "li"])
            snippet = ""
            if parent:
                p = parent.find("p")
                if p:
                    snippet = p.get_text(strip=True)
            articles.append({"title": text, "link": href, "description": snippet})
        return articles
    except Exception as e:
        print(f"HTML fail {url}: {e}")
        return []


def pick_article():
    all_articles = []
    for src in SOURCES:
        if src["type"] == "rss":
            all_articles.extend(fetch_rss(src["url"]))
        else:
            all_articles.extend(fetch_html_articles(src["url"]))
    if not all_articles:
        return FALLBACK
    article = random.choice(all_articles)
    return article


def send_telegram(article):
    now = datetime.now().strftime("%A, %B %d, %Y")
    msg = f"\U0001f4da *Daily Business Case Study*\n_{now}_\n\n"
    msg += f"*{article['title']}*\n\n"
    desc = article.get("description", "")
    if desc:
        desc = re.sub(r"\s+", " ", desc).strip()
        if len(desc) > 500:
            desc = desc[:500] + "..."
        msg += desc + "\n\n"
    msg += f"\U0001f517 [Read full article]({article['link']})\n\n"
    msg += "_\u2014 Harvard \u00b7 MIT \u00b7 Stanford \u00b7 Wharton \u00b7 Kellogg_"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"Sent: {article['title']}")


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        exit(1)
    article = pick_article()
    send_telegram(article)
