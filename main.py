import json
import time
from pathlib import Path

import feedparser

from config import DEFAULT_TOPIC, RSS_SOURCES

OUTPUT_FILE = Path("data/raw_articles/articles.json")
KEYWORDS_FILE = Path("config/keywords.json")
ARTICLES_PER_SOURCE = 5


def load_keywords():
    with KEYWORDS_FILE.open("r", encoding="utf-8") as file:
        keywords_by_topic = json.load(file)

    keywords = keywords_by_topic.get(DEFAULT_TOPIC)

    if keywords is None:
        print(f"Warning: No keywords found for topic '{DEFAULT_TOPIC}'.")
        return []

    print(f"Loaded {len(keywords)} keywords for topic: {DEFAULT_TOPIC}")
    return keywords


def find_matched_keywords(title, keywords):
    matched_keywords = []
    title_lower = title.lower()

    for keyword in keywords:
        if keyword.lower() in title_lower:
            matched_keywords.append(keyword)

    return matched_keywords


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
            title = entry.get("title", "")
            article = {
                "title": title,
                "url": entry.get("link", ""),
                "source": source["name"],
                "published_date": get_published_date(entry),
                "topic": DEFAULT_TOPIC
            }
            articles.append(article)

    return articles


def filter_articles_by_keywords(articles, keywords):
    relevant_articles = []

    for article in articles:
        matched_keywords = find_matched_keywords(article["title"], keywords)

        if matched_keywords:
            article["matched_keywords"] = matched_keywords
            relevant_articles.append(article)

    return relevant_articles


def save_articles(articles):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(articles, file, indent=2)


def main():
    print("Market Intelligence Agent started.")
    print(f"Topic: {DEFAULT_TOPIC}")

    keywords = load_keywords()
    articles = fetch_articles_from_rss()
    relevant_articles = filter_articles_by_keywords(articles, keywords)
    save_articles(relevant_articles)

    print(f"Fetched {len(articles)} articles from RSS sources.")
    print(f"Kept {len(relevant_articles)} relevant articles after keyword filtering.")
    print(f"Saved {len(relevant_articles)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
