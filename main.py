import json
import time
from pathlib import Path

import feedparser

from config import DEFAULT_TOPIC, RSS_SOURCES

OUTPUT_FILE = Path("data/raw_articles/articles.json")
ARTICLES_PER_SOURCE = 5


def get_published_date(entry):
    if entry.get("published_parsed"):
        return time.strftime("%Y-%m-%d", entry.published_parsed)

    if entry.get("updated_parsed"):
        return time.strftime("%Y-%m-%d", entry.updated_parsed)

    return entry.get("published", entry.get("updated", ""))


def fetch_articles_from_rss():
    articles = []

    for source in RSS_SOURCES:
        feed = feedparser.parse(source["url"])
        entries = feed.entries[:ARTICLES_PER_SOURCE]

        if not entries:
            print(f"Warning: No articles found for {source['name']}.")
            continue

        for entry in entries:
            article = {
                "title": entry.get("title", ""),
                "url": entry.get("link", ""),
                "source": source["name"],
                "published_date": get_published_date(entry),
                "topic": DEFAULT_TOPIC
            }
            articles.append(article)

    return articles


def save_articles(articles):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(articles, file, indent=2)


def main():
    print("Market Intelligence Agent started.")
    print(f"Topic: {DEFAULT_TOPIC}")

    articles = fetch_articles_from_rss()
    save_articles(articles)

    print(f"Fetched {len(articles)} articles from RSS sources.")
    print(f"Saved {len(articles)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
