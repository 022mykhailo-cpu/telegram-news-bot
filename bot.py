import os
import json
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHANNEL = os.environ["CHANNEL_ID"]

FEEDS = [
    "https://feeds.bbci.co.uk/ukrainian/rss.xml",
    "https://www.ukrinform.ua/rss/block-lastnews",
]

SEEN_FILE = "seen.json"


def get_text(element, names):
    for child in element.iter():
        tag = child.tag.split("}")[-1].lower()
        if tag in names and child.text:
            return child.text.strip()
    return ""


def get_link(element):
    for child in element:
        if child.tag.split("}")[-1].lower() == "link":
            href = child.attrib.get("href")
            if href:
                return href
            if child.text:
                return child.text.strip()
    return ""


def clean_text(value):
    value = re.sub(r"<[^>]+>", " ", value)
    return html.unescape(re.sub(r"\s+", " ", value)).strip()


def get_news(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "TelegramNewsBot/1.0"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        root = ET.fromstring(response.read())

    entries = root.findall(".//item")
    if not entries:
        entries = root.findall(".//{*}entry")

    news = []
    for item in entries:
        title = get_text(item, ["title"])
        link = get_link(item)
        description = get_text(
            item, ["description", "summary", "encoded"]
        )
        uid = get_text(item, ["guid", "id"]) or link

        if title and link and uid:
            news.append({
                "id": uid,
                "title": clean_text(title),
                "description": clean_text(description)[:600],
                "link": link,
            })

    return news


def send_news(item):
    message = (
        f"<b>{html.escape(item['title'])}</b>\n\n"
        f"{html.escape(item['description'])}\n\n"
        f'<a href="{html.escape(item["link"], quote=True)}">'
        "Читати повністю</a>"
    )

    data = json.dumps({
        "chat_id": CHANNEL,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        result = json.loads(response.read())

    if not result.get("ok"):
        raise RuntimeError("Telegram не прийняв повідомлення")


def main():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as file:
            seen = set(json.load(file))
        first_run = False
    else:
        seen = set()
        first_run = True

    for feed in FEEDS:
        try:
            news = get_news(feed)
            print(f"Отримано новин: {len(news)}")

            if first_run:
                seen.update(item["id"] for item in news)
                continue

            for item in reversed(news):
                if item["id"] in seen:
                    continue

                send_news(item)
                seen.add(item["id"])
                print("Опубліковано:", item["title"])

        except Exception as error:
            print(f"Помилка RSS {feed}: {error}")

    with open(SEEN_FILE, "w", encoding="utf-8") as file:
        json.dump(list(seen)[-2000:], file, ensure_ascii=False)


if __name__ == "__main__":
    main()
