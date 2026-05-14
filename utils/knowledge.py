import json
from datetime import datetime
from pathlib import Path


KNOWLEDGE_DIR = Path("data/knowledge")
ARTICLES_KNOWLEDGE_FILE = KNOWLEDGE_DIR / "articles_knowledge.json"
MARKET_INSIGHTS_FILE = KNOWLEDGE_DIR / "market_insights.json"
SOURCE_INDEX_FILE = KNOWLEDGE_DIR / "source_index.json"


def get_now_string() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_json_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        with path.open("w", encoding="utf-8") as file:
            json.dump({}, file, indent=2, ensure_ascii=False)


def ensure_knowledge_files() -> dict:
    paths = {
        "articles": str(ARTICLES_KNOWLEDGE_FILE),
        "insights": str(MARKET_INSIGHTS_FILE),
        "sources": str(SOURCE_INDEX_FILE)
    }

    for path in paths.values():
        ensure_json_file(Path(path))

    return paths


def load_json(path: str) -> dict:
    json_path = Path(path)

    if not json_path.exists():
        return {}

    try:
        with json_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Warning: Knowledge file is not valid JSON: {path}")
        return {}
    except OSError as error:
        print(f"Warning: Could not read knowledge file {path}: {error}")
        return {}


def save_json(path: str, data: dict) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def get_summary_field(summary_result: dict, field: str, default):
    if not summary_result:
        return default

    return summary_result.get(field, default)


def get_ranking_field(ranking_result: dict, field: str, default):
    if not ranking_result:
        return default

    return ranking_result.get(field, default)


def upsert_article_knowledge(
    article: dict,
    summary_result: dict,
    ranking_result: dict,
    knowledge: dict
) -> dict:
    url = article.get("url", "")

    if not url:
        return knowledge

    existing = knowledge.get(url, {})
    now = get_now_string()
    ai_summary = summary_result or {}
    ranking = ranking_result or {}

    entry = {
        "url": url,
        "title": article.get("title", existing.get("title", "")),
        "topic": article.get("topic", existing.get("topic", "")),
        "source": article.get("source", existing.get("source", "")),
        "source_category": article.get(
            "source_category",
            existing.get("source_category", "")
        ),
        "source_type": article.get("source_type", existing.get("source_type", "rss")),
        "web_mode": article.get("web_mode", existing.get("web_mode")),
        "published_date": article.get(
            "published_date",
            existing.get("published_date", "")
        ),
        "first_seen": article.get("first_seen", existing.get("first_seen", "")),
        "last_seen": article.get("last_seen", existing.get("last_seen", "")),
        "seen_count": article.get("seen_count", existing.get("seen_count", 0)),
        "content_hash": article.get(
            "content_hash",
            existing.get("content_hash", "")
        ),
        "freshness_status": article.get(
            "freshness_status",
            existing.get("freshness_status", "unknown")
        ),
        "summary": get_summary_field(
            ai_summary,
            "summary",
            existing.get("summary", "")
        ),
        "key_points": get_summary_field(
            ai_summary,
            "key_points",
            existing.get("key_points", [])
        ),
        "why_it_matters": get_summary_field(
            ai_summary,
            "why_it_matters",
            existing.get("why_it_matters", "")
        ),
        "score": article.get("score", existing.get("score", 0)),
        "recommendation": article.get(
            "recommendation",
            existing.get("recommendation", "Exclude")
        ),
        "relevance": get_ranking_field(
            ranking,
            "relevance",
            existing.get("relevance", 0)
        ),
        "use_case_clarity": get_ranking_field(
            ranking,
            "use_case_clarity",
            existing.get("use_case_clarity", 0)
        ),
        "problem_solution_fit": get_ranking_field(
            ranking,
            "problem_solution_fit",
            existing.get("problem_solution_fit", 0)
        ),
        "actionability": get_ranking_field(
            ranking,
            "actionability",
            existing.get("actionability", 0)
        ),
        "credibility_novelty": get_ranking_field(
            ranking,
            "credibility_novelty",
            existing.get("credibility_novelty", 0)
        ),
        "use_case": get_ranking_field(
            ranking,
            "use_case",
            existing.get("use_case", "")
        ),
        "problem_solved": get_ranking_field(
            ranking,
            "problem_solved",
            existing.get("problem_solved", "")
        ),
        "reason": get_ranking_field(
            ranking,
            "reason",
            existing.get("reason", "")
        ),
        "tags": existing.get("tags", []),
        "updated_at": now
    }

    knowledge[url] = entry
    return knowledge


def get_related_sources(ranked_articles: list) -> list:
    related_sources = []

    for article in ranked_articles:
        recommendation = article.get("recommendation", "")

        if recommendation not in ["Core", "Useful", "Background"]:
            continue

        related_sources.append({
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "recommendation": recommendation
        })

    return related_sources


def update_market_insights(
    topic: str,
    week_key: str,
    ranked_articles: list,
    report_path: str,
    slide_path: str,
    insights: dict
) -> dict:
    key = f"{topic}_{week_key}"
    insights[key] = {
        "topic": topic,
        "week": week_key,
        "report_path": report_path,
        "slide_path": slide_path,
        "related_sources": get_related_sources(ranked_articles),
        "created_at": get_now_string()
    }

    return insights


def get_source_status(source: dict) -> str:
    last_status = source.get("last_status")

    if last_status in ["active", "skipped", "failed", "static", "listing"]:
        return last_status

    if source.get("type", "rss") == "web":
        web_mode = source.get("web_mode")

        if web_mode == "static":
            return "static"

        if web_mode == "listing":
            return "listing"

        return "skipped"

    return "active"


def update_source_index(
    topic: str,
    sources: list,
    source_index: dict
) -> dict:
    now = get_now_string()

    for source in sources:
        name = source.get("name", "")

        if not name:
            continue

        existing = source_index.get(name, {})
        topics = existing.get("topics", [])

        if topic not in topics:
            topics.append(topic)

        source_index[name] = {
            "name": name,
            "url": source.get("url", existing.get("url", "")),
            "category": source.get("category", existing.get("category", "")),
            "type": source.get("type", existing.get("type", "rss")),
            "web_mode": source.get("web_mode", existing.get("web_mode")),
            "topics": topics,
            "last_checked": now,
            "status": get_source_status(source),
            "last_entries_count": source.get(
                "last_entries_count",
                existing.get("last_entries_count", 0)
            )
        }

    return source_index
