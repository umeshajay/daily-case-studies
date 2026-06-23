import json
import os
import random
import re
import requests
from datetime import datetime
from xml.etree import ElementTree
from bs4 import BeautifulSoup

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HISTORY_FILE = "sent_history.json"

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
    "summary": "How great companies bring dignity, pay, and meaning to every employee.",
}


def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)


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
                raw = item.get("summary") or item.get("content_text") or ""
                desc = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True) if raw else ""
                if title:
                    articles.append({"title": title, "summary": desc})
            return articles
        root = ElementTree.fromstring(resp.content)
        articles = []
        for item in root.iter("item"):
            title = item.findtext("title", "").strip()
            desc = BeautifulSoup(item.findtext("description", "") or "", "html.parser").get_text(separator=" ", strip=True)
            if title:
                articles.append({"title": title, "summary": desc})
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.iter(f"{{{atom_ns}}}entry"):
            title = entry.findtext(f"{{{atom_ns}}}title", "").strip()
            desc = entry.findtext(f"{{{atom_ns}}}summary", "")
            if desc:
                desc = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
            if title:
                articles.append({"title": title, "summary": desc})
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
            text = tag.get_text(strip=True)
            if not text or len(text) < 20:
                continue
            if text in seen:
                continue
            seen.add(text)
            parent = tag.find_parent(["article", "div", "li"])
            snippet = ""
            if parent:
                p = parent.find("p")
                if p:
                    snippet = p.get_text(strip=True)
            articles.append({"title": text, "summary": snippet})
        return articles
    except Exception as e:
        print(f"HTML fail {url}: {e}")
        return []


def pick_article(sent_titles):
    seen = set(sent_titles)
    all_articles = []
    for src in SOURCES:
        if src["type"] == "rss":
            all_articles.extend(fetch_rss(src["url"]))
        else:
            all_articles.extend(fetch_html_articles(src["url"]))
    fresh = [a for a in all_articles if a["title"] not in seen]
    if not fresh:
        fresh = all_articles
    if not fresh:
        return FALLBACK
    return random.choice(fresh)


def summarize(text, max_len=400):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def send_telegram(title, summary):
    now = datetime.now().strftime("%A, %d %B %Y")
    msg = f"\U0001f4da *Daily Business Case Study*\n_{now}_\n\n*{title}*\n\n{summary}"
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": msg,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"Sent: {title}")


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        exit(1)
    history = load_history()
    article = pick_article(history)
    summary = summarize(article.get("summary", ""))
    send_telegram(article["title"], summary)
    history.append(article["title"])
    save_history(history)
