import json
from pathlib import Path

from config import DEFAULT_TOPIC, SOURCES


OUTPUT_FILE = Path("data/raw_articles/articles.json")


def create_mock_articles():
    return [
        {
            "title": "OpenAI introduces new agent capabilities for enterprise teams",
            "url": "https://openai.com/news/mock-agent-capabilities",
            "source": SOURCES[0]["name"],
            "published_date": "2026-05-01",
            "topic": DEFAULT_TOPIC
        },
        {
            "title": "Anthropic shares guidance on AI agents in business workflows",
            "url": "https://www.anthropic.com/news/mock-business-workflows",
            "source": SOURCES[1]["name"],
            "published_date": "2026-05-02",
            "topic": DEFAULT_TOPIC
        },
        {
            "title": "Google Cloud highlights agent tools for SaaS operations",
            "url": "https://cloud.google.com/blog/mock-agent-tools-saas",
            "source": SOURCES[2]["name"],
            "published_date": "2026-05-03",
            "topic": DEFAULT_TOPIC
        },
        {
            "title": "AWS explains how companies can deploy AI agents at scale",
            "url": "https://aws.amazon.com/blogs/mock-ai-agents-scale",
            "source": SOURCES[3]["name"],
            "published_date": "2026-05-04",
            "topic": DEFAULT_TOPIC
        },
        {
            "title": "Microsoft Azure explores agentic automation for B2B SaaS",
            "url": "https://azure.microsoft.com/en-us/blog/mock-agentic-automation",
            "source": SOURCES[4]["name"],
            "published_date": "2026-05-05",
            "topic": DEFAULT_TOPIC
        }
    ]


def save_articles(articles):
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as file:
        json.dump(articles, file, indent=2)


def main():
    articles = create_mock_articles()
    save_articles(articles)

    print("Market Intelligence Agent started.")
    print(f"Topic: {DEFAULT_TOPIC}")
    print(f"Saved {len(articles)} articles to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
