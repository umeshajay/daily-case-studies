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
CACHE_FILE = "case_studies_cache.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}


def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f)


def fetch_hbr_case_urls():
    try:
        r = requests.get(
            "https://hbr.org/search?term=case+study&searchLocation=articles",
            headers=HEADERS, timeout=15
        )
        paths = set(re.findall(r'href="(/202\d/\d{2}/case-study-[\w-]+)"', r.text))
        return sorted("https://hbr.org" + p for p in paths)
    except Exception as e:
        print(f"HBR search fail: {e}")
        return []


def fetch_hbr_case_meta(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        text = r.text
        title_m = re.search(r'<title>([^<]+)', text)
        title = title_m.group(1).replace(" - Harvard Business Review", "").strip() if title_m else ""
        desc_m = re.search(r'<meta name="description" content="([^"]+)"', text)
        desc = desc_m.group(1) if desc_m else ""
        if not desc:
            desc_m = re.search(r'<meta property="og:description" content="([^"]+)"', text)
            desc = desc_m.group(1) if desc_m else ""
        return title, desc
    except Exception as e:
        print(f"HBR fetch fail {url}: {e}")
        return "", ""


def build_hbr_cases():
    urls = fetch_hbr_case_urls()
    cases = []
    for url in urls:
        title, summary = fetch_hbr_case_meta(url)
        if not title:
            slug = url.rstrip("/").split("/")[-1]
            title = slug.replace("case-study-", "").replace("-", " ").title()
        cases.append({
            "title": title,
            "summary": summary,
            "url": url,
            "source": "Harvard Business Review"
        })
    return cases


def build_supplementary_cases():
    cases = []
    sources = [
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
    for src in sources:
        try:
            if src["type"] == "rss":
                r = requests.get(src["url"], headers=HEADERS, timeout=15)
                r.raise_for_status()
                ctype = r.headers.get("content-type", "")
                if "json" in ctype:
                    data = r.json()
                    for item in data.get("items", [])[:5]:
                        raw = item.get("summary") or item.get("content_text") or ""
                        desc = BeautifulSoup(raw, "html.parser").get_text(separator=" ", strip=True) if raw else ""
                        cases.append({
                            "title": item.get("title", "").strip(),
                            "summary": desc,
                            "url": item.get("url", ""),
                            "source": src["name"],
                        })
                else:
                    root = ElementTree.fromstring(r.content)
                    for item in root.iter("item"):
                        title = item.findtext("title", "").strip()
                        desc_raw = item.findtext("description", "") or ""
                        desc = BeautifulSoup(desc_raw, "html.parser").get_text(separator=" ", strip=True)
                        cases.append({
                            "title": title,
                            "summary": desc,
                            "url": item.findtext("link", "").strip(),
                            "source": src["name"],
                        })
                        if len([c for c in cases if c["source"] == src["name"]]) >= 5:
                            break
            elif src["type"] == "html":
                r = requests.get(src["url"], headers=HEADERS, timeout=15)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, "html.parser")
                count = 0
                for tag in soup.select("a[href]"):
                    text = tag.get_text(strip=True)
                    href = tag.get("href", "")
                    if not text or len(text) < 20:
                        continue
                    if "insights" not in href and "gsb.stanford.edu" not in href:
                        continue
                    if not href.startswith("http"):
                        href = requests.compat.urljoin(src["url"], href)
                    parent = tag.find_parent(["article"])
                    snippet = ""
                    if parent:
                        p = parent.find("p")
                        if p:
                            snippet = p.get_text(strip=True)
                    cases.append({
                        "title": text,
                        "summary": snippet,
                        "url": href,
                        "source": src["name"],
                    })
                    count += 1
                    if count >= 5:
                        break
        except Exception as e:
            print(f"Skip {src['name']}: {e}")
    return cases


def is_good_case(c):
    title = c.get("title", "")
    if len(title) < 15:
        return False
    bad = ["sign up", "subscribe", "search", "login", "cookie", "privacy", "follow us", "insightsby stanford", "government &", "leadership &", "climate &"]
    if any(b in title.lower() for b in bad):
        return False
    return True


def build_master_list():
    cached = load_json(CACHE_FILE)
    if cached:
        return cached
    hbr = build_hbr_cases()
    supp = build_supplementary_cases()
    master = [c for c in hbr + supp if is_good_case(c)]
    random.shuffle(master)
    save_json(CACHE_FILE, master)
    return master


def pick_case(master, sent_titles):
    seen = set(sent_titles)
    fresh = [c for c in master if c["title"] not in seen]
    if not fresh:
        fresh = master
    if not fresh:
        return {"title": "No cases available", "summary": "Could not fetch case studies.", "source": ""}
    return random.choice(fresh)


def summarize(text, max_len=500):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def send_telegram(title, summary, source):
    now = datetime.now().strftime("%A, %d %B %Y")
    msg = (
        f"\U0001f4da *Daily Business Case Study*\n"
        f"_{now}_\n\n"
        f"*{title}*\n\n"
        f"{summary}\n\n"
        f"_\u2014 {source}_"
    )
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    print(f"Sent: {title}")


if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID")
        exit(1)
    master = build_master_list()
    history = load_json(HISTORY_FILE)
    case = pick_case(master, history)
    summary = summarize(case.get("summary", ""))
    send_telegram(case["title"], summary, case.get("source", "Top Business School"))
    history.append(case["title"])
    save_json(HISTORY_FILE, history)
