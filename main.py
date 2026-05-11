import json
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", category=FutureWarning)

import feedparser
import trafilatura
from dotenv import load_dotenv

load_dotenv()

from config import DEFAULT_TOPIC, LLM_PROVIDER, RSS_SOURCES
from llm.gemini_provider import GeminiProvider
from llm.openai_provider import OpenAIProvider

RAW_OUTPUT_FILE = Path("data/raw_articles/articles.json")
CLEAN_OUTPUT_FILE = Path("data/clean_articles/clean_articles.json")
MARKET_BRIEF_FILE = Path("outputs/reports/market_brief.md")
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


def save_articles(articles, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        json.dump(articles, file, indent=2)


def load_articles(input_file):
    with input_file.open("r", encoding="utf-8") as file:
        return json.load(file)


def extract_content(article):
    content = ""
    extraction_status = "failed"

    try:
        downloaded = trafilatura.fetch_url(article["url"])

        if downloaded:
            extracted_content = trafilatura.extract(downloaded)

            if extracted_content:
                content = extracted_content
                extraction_status = "success"
    except Exception as error:
        print(f"Warning: Could not extract content from {article['url']}: {error}")

    clean_article = {
        "title": article["title"],
        "url": article["url"],
        "source": article["source"],
        "published_date": article["published_date"],
        "topic": article["topic"],
        "matched_keywords": article["matched_keywords"],
        "content": content,
        "content_length": len(content),
        "extraction_status": extraction_status
    }

    return clean_article


def extract_articles_content(articles):
    clean_articles = []

    for article in articles:
        clean_article = extract_content(article)
        clean_articles.append(clean_article)

    return clean_articles


def get_articles_ready_for_brief(articles):
    ready_articles = []

    for article in articles:
        if article["extraction_status"] == "success" and article["content"]:
            ready_articles.append(article)

    return ready_articles


def get_llm_provider():
    if LLM_PROVIDER == "gemini":
        return GeminiProvider()

    if LLM_PROVIDER == "openai":
        return OpenAIProvider()

    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def summarize_articles(articles, provider):
    summarized_articles = []
    successful_summaries = 0

    for article in articles:
        try:
            ai_summary = provider.summarize_article(article)
        except Exception as error:
            ai_summary = {
                "summary": "",
                "key_points": [],
                "why_it_matters": "",
                "error": str(error)
            }

        if "error" not in ai_summary:
            successful_summaries += 1

        article_with_summary = article.copy()
        article_with_summary["ai_summary"] = ai_summary
        summarized_articles.append(article_with_summary)

    return summarized_articles, successful_summaries


def create_market_brief(articles):
    lines = [
        "# Market Brief",
        "",
        f"Topic: {DEFAULT_TOPIC}",
        "",
        f"Articles included: {len(articles)}",
        ""
    ]

    for index, article in enumerate(articles, start=1):
        matched_keywords = ", ".join(article["matched_keywords"])
        ai_summary = article["ai_summary"]
        key_points = ai_summary.get("key_points", [])

        lines.extend([
            f"## {index}. {article['title']}",
            "",
            f"- Source: {article['source']}",
            f"- Published date: {article['published_date']}",
            f"- URL: {article['url']}",
            f"- Matched keywords: {matched_keywords}",
            f"- Content length: {article['content_length']}",
            "",
            "### AI Summary",
            "",
            ai_summary.get("summary", ""),
            "",
            "### Key Points",
            ""
        ])

        if key_points:
            for key_point in key_points:
                lines.append(f"- {key_point}")
        else:
            lines.append("- No key points available.")

        lines.extend([
            "",
            "### Why It Matters",
            "",
            ai_summary.get("why_it_matters", ""),
            ""
        ])

        if ai_summary.get("error"):
            lines.extend([
                "### Error",
                "",
                ai_summary["error"],
                ""
            ])

    return "\n".join(lines)


def save_markdown(content, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        file.write(content)


def main():
    print("Market Intelligence Agent started.")
    print(f"Topic: {DEFAULT_TOPIC}")

    keywords = load_keywords()
    articles = fetch_articles_from_rss()
    relevant_articles = filter_articles_by_keywords(articles, keywords)
    save_articles(relevant_articles, RAW_OUTPUT_FILE)

    print(f"Fetched {len(articles)} articles from RSS sources.")
    print(f"Kept {len(relevant_articles)} relevant articles after keyword filtering.")
    print(f"Saved {len(relevant_articles)} articles to {RAW_OUTPUT_FILE}")

    raw_articles = load_articles(RAW_OUTPUT_FILE)
    clean_articles = extract_articles_content(raw_articles)
    successful_extractions = 0

    for article in clean_articles:
        if article["extraction_status"] == "success":
            successful_extractions += 1

    save_articles(clean_articles, CLEAN_OUTPUT_FILE)

    print(f"Extracted content for {successful_extractions}/{len(raw_articles)} articles.")
    print(f"Saved clean articles to {CLEAN_OUTPUT_FILE}")

    clean_articles = load_articles(CLEAN_OUTPUT_FILE)
    articles_ready_for_brief = get_articles_ready_for_brief(clean_articles)
    provider = get_llm_provider()

    print(f"Using LLM provider: {LLM_PROVIDER}")

    summarized_articles, successful_summaries = summarize_articles(
        articles_ready_for_brief,
        provider
    )
    market_brief = create_market_brief(summarized_articles)
    save_markdown(market_brief, MARKET_BRIEF_FILE)

    print(f"Generated AI summaries for {successful_summaries} articles.")
    print(f"Saved market brief to {MARKET_BRIEF_FILE}")


if __name__ == "__main__":
    main()
