import argparse
import json
import time
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL.*")
warnings.filterwarnings("ignore", category=FutureWarning)

import feedparser
import trafilatura
from dotenv import load_dotenv

load_dotenv()

from config import (
    DEFAULT_TOPIC,
    FRESHNESS_ALLOWED_STATUSES,
    FRESHNESS_EXCLUDED_STATUSES,
    LLM_MODEL,
    LLM_PROVIDER,
    MAX_ARTICLES_PER_RUN,
    REPORT_LOOKBACK_DAYS,
    REPORT_TEMPLATE,
    SLIDE_DRAFT_ENABLED,
    RSS_SOURCES_BY_TOPIC
)
from llm.gemini_provider import GeminiProvider
from llm.openai_provider import OpenAIProvider
from utils.cache import (
    get_cache_paths,
    get_cached_result,
    get_current_week_key,
    load_json_cache,
    save_json_cache,
    set_cached_result
)
from utils.history import (
    determine_freshness_status,
    generate_content_hash,
    load_processed_history,
    save_processed_history,
    update_processed_history
)
from utils.web import fetch_listing_links

RAW_OUTPUT_FILE = Path("data/raw_articles/articles.json")
CLEAN_OUTPUT_FILE = Path("data/clean_articles/clean_articles.json")
MARKET_BRIEF_FILE = Path("outputs/reports/market_brief.md")
RANKED_SOURCES_FILE = Path("outputs/reports/ranked_sources.md")
MARKET_ANALYSIS_REPORT_FILE = Path("outputs/reports/market_analysis_report.md")
SLIDE_DRAFT_FILE = Path("outputs/slides/slide_draft.md")
KEYWORDS_FILE = Path("config/keywords.json")
PROCESSED_HISTORY_FILE = Path("data/history/processed_articles.json")
ARTICLES_PER_SOURCE = 5
MAX_SCORE = 37.5
RUNTIME_TOPIC = DEFAULT_TOPIC


def get_current_topic():
    return RUNTIME_TOPIC


def get_resolved_topic():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topic",
        help="Topic to run, for example: AI, FinOps, ProductObservation"
    )
    args = parser.parse_args()

    if args.topic:
        return args.topic

    return DEFAULT_TOPIC


def load_keywords():
    with KEYWORDS_FILE.open("r", encoding="utf-8") as file:
        keywords_by_topic = json.load(file)

    topic = get_current_topic()
    keywords = keywords_by_topic.get(topic)

    if keywords is None:
        print(f"Warning: No keywords found for topic '{topic}'.")
        return []

    print(f"Loaded {len(keywords)} keywords for topic: {topic}")
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


def get_sources_for_topic(topic):
    sources = RSS_SOURCES_BY_TOPIC.get(topic)

    if sources is None:
        print(f"Warning: No RSS sources found for topic: {topic}")
        sources = []

    print(f"Loaded {len(sources)} sources for topic: {topic}")
    return sources


def fetch_articles_from_rss():
    articles = []
    static_web_count = 0
    listing_web_count = 0
    topic = get_current_topic()
    sources = get_sources_for_topic(topic)

    for source in sources:
        source_type = source.get("type")

        if not source_type:
            print(
                f"Warning: source type missing for {source['name']}; "
                "defaulting to rss"
            )
            source_type = "rss"

        if source_type == "web":
            web_mode = source.get("web_mode")

            if web_mode == "static":
                article = {
                    "title": source["name"],
                    "url": source["url"],
                    "source": source["name"],
                    "source_category": source.get("category", ""),
                    "source_type": "web",
                    "web_mode": "static",
                    "published_date": "",
                    "topic": topic,
                    "matched_keywords": []
                }
                articles.append(article)
                static_web_count += 1
                print(f"Added static web source: {source['name']}")
            elif web_mode == "listing":
                try:
                    listing_articles = fetch_listing_links(source, topic)
                except Exception:
                    print(
                        "Warning: Could not parse listing web source: "
                        f"{source['name']}"
                    )
                    continue

                if not listing_articles:
                    print(
                        "Warning: No article links found for listing web source: "
                        f"{source['name']}"
                    )
                    continue

                articles.extend(listing_articles)
                listing_web_count += len(listing_articles)
                print(
                    f"Parsed {len(listing_articles)} links from listing web source: "
                    f"{source['name']}"
                )
            else:
                print(
                    "Warning: web_mode missing for web source: "
                    f"{source['name']}"
                )

            continue

        try:
            feed = feedparser.parse(source["url"])
            entries = feed.entries[:ARTICLES_PER_SOURCE]
        except Exception:
            print(f"Warning: Could not fetch or parse source: {source['name']}")
            continue

        if feed.get("bozo") and not entries:
            print(f"Warning: Could not fetch or parse source: {source['name']}")
            continue

        if not entries:
            print(f"Warning: Could not fetch or parse source: {source['name']}")
            continue

        for entry in entries:
            title = entry.get("title", "")
            article = {
                "title": title,
                "url": entry.get("link", ""),
                "source": source["name"],
                "source_category": source.get("category", ""),
                "source_type": source_type,
                "web_mode": source.get("web_mode"),
                "published_date": get_published_date(entry),
                "topic": topic
            }
            articles.append(article)

    return articles, static_web_count, listing_web_count


def filter_articles_by_keywords(articles, keywords):
    relevant_articles = []

    for article in articles:
        if article.get("source_type") == "web" and article.get("web_mode") == "static":
            relevant_articles.append(article)
            continue

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
        "source_category": article.get("source_category", ""),
        "source_type": article.get("source_type", "rss"),
        "web_mode": article.get("web_mode"),
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


def enrich_articles_with_freshness(articles):
    history = load_processed_history(str(PROCESSED_HISTORY_FILE))
    enriched_articles = []

    for article in articles:
        article_with_freshness = article.copy()
        content_hash = generate_content_hash(article_with_freshness.get("content", ""))
        article_with_freshness["content_hash"] = content_hash

        freshness_status = determine_freshness_status(
            article_with_freshness,
            history,
            REPORT_LOOKBACK_DAYS
        )
        article_with_freshness["freshness_status"] = freshness_status

        history = update_processed_history(
            article_with_freshness,
            history,
            freshness_status
        )

        history_entry = history.get(article_with_freshness.get("url", ""), {})
        article_with_freshness["first_seen"] = history_entry.get("first_seen", "")
        article_with_freshness["last_seen"] = history_entry.get("last_seen", "")
        article_with_freshness["seen_count"] = history_entry.get("seen_count", 0)

        enriched_articles.append(article_with_freshness)

    save_processed_history(str(PROCESSED_HISTORY_FILE), history)
    return enriched_articles


def print_freshness_summary(articles):
    counts = {
        "new": 0,
        "updated": 0,
        "unknown": 0,
        "repeated": 0,
        "old": 0
    }

    for article in articles:
        status = article.get("freshness_status", "unknown")
        counts[status] = counts.get(status, 0) + 1

    print("Freshness summary:")
    print(f"- New: {counts.get('new', 0)}")
    print(f"- Updated: {counts.get('updated', 0)}")
    print(f"- Unknown: {counts.get('unknown', 0)}")
    print(f"- Repeated: {counts.get('repeated', 0)}")
    print(f"- Old: {counts.get('old', 0)}")

    excluded_count = sum(
        1 for article in articles
        if article.get("freshness_status") in FRESHNESS_EXCLUDED_STATUSES
    )

    if excluded_count:
        print(
            f"Excluded {excluded_count} repeated/old articles from "
            "this week's report."
        )

    if counts.get("new", 0) + counts.get("updated", 0) == 0:
        print("No new or updated articles found for this run.")


def get_articles_ready_for_brief(articles):
    ready_articles = []

    for article in articles:
        if article.get("freshness_status") not in FRESHNESS_ALLOWED_STATUSES:
            continue

        if article["extraction_status"] == "success" and article["content"]:
            ready_articles.append(article)

    return ready_articles


def limit_articles_for_llm(articles):
    freshness_priority = {
        "new": 3,
        "updated": 2,
        "unknown": 1
    }
    sorted_articles = sorted(
        articles,
        key=lambda article: (
            freshness_priority.get(article.get("freshness_status"), 0),
            len(article.get("matched_keywords", [])),
            article.get("content_length", 0)
        ),
        reverse=True
    )

    if len(sorted_articles) > MAX_ARTICLES_PER_RUN:
        print(f"Limiting LLM processing to {MAX_ARTICLES_PER_RUN} articles.")

    return sorted_articles[:MAX_ARTICLES_PER_RUN]


def get_llm_provider():
    if LLM_PROVIDER == "gemini":
        return GeminiProvider()

    if LLM_PROVIDER == "openai":
        return OpenAIProvider()

    raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")


def is_successful_summary(ai_summary):
    if ai_summary.get("error"):
        return False

    return bool(ai_summary.get("summary"))


def get_cached_at():
    return datetime.now().replace(microsecond=0).isoformat()


def get_provider_model(provider):
    return getattr(provider, "last_model_used", LLM_MODEL)


def build_summary_cache_entry(article, ai_summary, provider, cache_period):
    return {
        "title": article["title"],
        "url": article["url"],
        "source": article["source"],
        "source_category": article.get("source_category", ""),
        "source_type": article.get("source_type", "rss"),
        "web_mode": article.get("web_mode"),
        "published_date": article["published_date"],
        "topic": article["topic"],
        "content_hash": article.get("content_hash", ""),
        "freshness_status": article.get("freshness_status", "unknown"),
        "model": get_provider_model(provider),
        "summary": ai_summary.get("summary", ""),
        "key_points": ai_summary.get("key_points", []),
        "why_it_matters": ai_summary.get("why_it_matters", ""),
        "cached_at": get_cached_at(),
        "cache_period": cache_period
    }


def can_use_cached_llm_result(cached_result, article):
    if not cached_result:
        return False

    cached_hash = cached_result.get("content_hash", "")
    current_hash = article.get("content_hash", "")

    if cached_hash and current_hash and cached_hash != current_hash:
        return False

    if article.get("freshness_status") == "updated" and cached_hash != current_hash:
        return False

    return True


def get_summary_from_cache(cached_summary):
    return {
        "summary": cached_summary.get("summary", ""),
        "key_points": cached_summary.get("key_points", []),
        "why_it_matters": cached_summary.get("why_it_matters", "")
    }


def summarize_articles(
    articles,
    provider,
    summary_cache,
    summary_cache_path,
    cache_period
):
    summarized_articles = []
    successful_summaries = 0

    for article in articles:
        cached_summary = get_cached_result(summary_cache, article["url"])

        if can_use_cached_llm_result(cached_summary, article):
            ai_summary = get_summary_from_cache(cached_summary)
            print(f"Loaded summary from cache for: {article['title']}")
        else:
            cached_summary = None
            try:
                ai_summary = provider.summarize_article(article)
            except Exception as error:
                ai_summary = {
                    "summary": "",
                    "key_points": [],
                    "why_it_matters": "",
                    "error": str(error)
                }

        if ai_summary.get("error"):
            short_error = str(ai_summary["error"]).splitlines()[0][:160]
            print(
                f"Warning: AI summary failed for '{article['title']}': "
                f"{short_error}"
            )

        if is_successful_summary(ai_summary):
            successful_summaries += 1

            if not cached_summary:
                cache_entry = build_summary_cache_entry(
                    article,
                    ai_summary,
                    provider,
                    cache_period
                )
                set_cached_result(summary_cache, article["url"], cache_entry)
                save_json_cache(summary_cache_path, summary_cache)
                print(f"Saved summary to cache for: {article['title']}")

        article_with_summary = article.copy()
        article_with_summary["ai_summary"] = ai_summary
        summarized_articles.append(article_with_summary)

    return summarized_articles, successful_summaries


def get_articles_ready_for_ranking(summarized_articles):
    articles_ready_for_ranking = []

    for article in summarized_articles:
        ai_summary = article.get("ai_summary", {})

        if is_successful_summary(ai_summary):
            articles_ready_for_ranking.append(article)
        else:
            print(
                "Skipping ranking for article due to summary error: "
                f"{article['title']}"
            )

    return articles_ready_for_ranking


def clamp_score(value):
    try:
        score = int(value)
    except (TypeError, ValueError):
        score = 1

    if score < 1:
        return 1

    if score > 5:
        return 5

    return score


def calculate_article_score(ranking):
    relevance = clamp_score(ranking.get("relevance"))
    use_case_clarity = clamp_score(ranking.get("use_case_clarity"))
    problem_solution_fit = clamp_score(ranking.get("problem_solution_fit"))
    actionability = clamp_score(ranking.get("actionability"))
    credibility_novelty = clamp_score(ranking.get("credibility_novelty"))

    weighted_score = (
        relevance * 1
        + use_case_clarity * 2
        + problem_solution_fit * 2
        + actionability * 1.5
        + credibility_novelty * 1
    )

    return round(weighted_score / MAX_SCORE * 100, 1)


def get_recommendation(score):
    if score >= 85:
        return "Core"

    if score >= 70:
        return "Useful"

    if score >= 55:
        return "Background"

    return "Exclude"


def build_ranking_cache_entry(
    article,
    ranking,
    score,
    recommendation,
    provider,
    cache_period
):
    return {
        "title": article["title"],
        "url": article["url"],
        "source": article["source"],
        "source_category": article.get("source_category", ""),
        "source_type": article.get("source_type", "rss"),
        "web_mode": article.get("web_mode"),
        "published_date": article["published_date"],
        "topic": article["topic"],
        "content_hash": article.get("content_hash", ""),
        "freshness_status": article.get("freshness_status", "unknown"),
        "model": get_provider_model(provider),
        "score": score,
        "recommendation": recommendation,
        "relevance": ranking.get("relevance", 1),
        "use_case_clarity": ranking.get("use_case_clarity", 1),
        "problem_solution_fit": ranking.get("problem_solution_fit", 1),
        "actionability": ranking.get("actionability", 1),
        "credibility_novelty": ranking.get("credibility_novelty", 1),
        "use_case": ranking.get("use_case", ""),
        "problem_solved": ranking.get("problem_solved", ""),
        "reason": ranking.get("reason", ""),
        "cached_at": get_cached_at(),
        "cache_period": cache_period
    }


def get_ranking_from_cache(cached_ranking):
    return {
        "relevance": cached_ranking.get("relevance", 1),
        "use_case_clarity": cached_ranking.get("use_case_clarity", 1),
        "problem_solution_fit": cached_ranking.get("problem_solution_fit", 1),
        "actionability": cached_ranking.get("actionability", 1),
        "credibility_novelty": cached_ranking.get("credibility_novelty", 1),
        "use_case": cached_ranking.get("use_case", ""),
        "problem_solved": cached_ranking.get("problem_solved", ""),
        "reason": cached_ranking.get("reason", "")
    }


def rank_articles(
    articles,
    provider,
    ranking_cache,
    ranking_cache_path,
    cache_period
):
    ranked_articles = []

    for article in articles:
        cached_ranking = get_cached_result(ranking_cache, article["url"])

        if can_use_cached_llm_result(cached_ranking, article):
            ranking = get_ranking_from_cache(cached_ranking)
            score = cached_ranking.get("score", 55.0)
            recommendation = cached_ranking.get("recommendation", "Background")
            print(f"Loaded ranking from cache for: {article['title']}")
        else:
            cached_ranking = None
            try:
                ranking = provider.rank_article(article)
            except Exception as error:
                ranking = {
                    "relevance": 1,
                    "use_case_clarity": 1,
                    "problem_solution_fit": 1,
                    "actionability": 1,
                    "credibility_novelty": 1,
                    "use_case": "",
                    "problem_solved": "",
                    "reason": str(error),
                    "error": str(error)
                }

            ranking["relevance"] = clamp_score(ranking.get("relevance"))
            ranking["use_case_clarity"] = clamp_score(ranking.get("use_case_clarity"))
            ranking["problem_solution_fit"] = clamp_score(ranking.get("problem_solution_fit"))
            ranking["actionability"] = clamp_score(ranking.get("actionability"))
            ranking["credibility_novelty"] = clamp_score(ranking.get("credibility_novelty"))

            if ranking.get("error"):
                score = 55.0
                recommendation = "Background"
                ranking["reason"] = ranking["error"]
            else:
                score = calculate_article_score(ranking)
                recommendation = get_recommendation(score)

                cache_entry = build_ranking_cache_entry(
                    article,
                    ranking,
                    score,
                    recommendation,
                    provider,
                    cache_period
                )
                set_cached_result(ranking_cache, article["url"], cache_entry)
                save_json_cache(ranking_cache_path, ranking_cache)
                print(f"Saved ranking to cache for: {article['title']}")

        article_with_ranking = article.copy()
        article_with_ranking["ranking"] = ranking
        article_with_ranking["score"] = score
        article_with_ranking["recommendation"] = recommendation
        ranked_articles.append(article_with_ranking)

    return sorted(ranked_articles, key=lambda item: item["score"], reverse=True)


def create_market_brief(articles):
    lines = [
        "# Market Brief",
        "",
        f"Topic: {get_current_topic()}",
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
            f"- Category: {article.get('source_category', '')}",
            f"- Type: {article.get('source_type', 'rss')}",
            f"- Web mode: {article.get('web_mode', '')}",
            f"- Published date: {article['published_date']}",
            f"- Freshness status: {article.get('freshness_status', 'unknown')}",
            f"- First seen: {article.get('first_seen', '')}",
            f"- Last seen: {article.get('last_seen', '')}",
            f"- Seen count: {article.get('seen_count', 0)}",
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


def create_ranked_sources_report(articles):
    lines = [
        "# Ranked Sources",
        "",
        f"Topic: {get_current_topic()}",
        "",
        f"Articles evaluated: {len(articles)}",
        ""
    ]

    for index, article in enumerate(articles, start=1):
        ranking = article["ranking"]
        content_hash = article.get("content_hash", "")

        lines.extend([
            f"## {index}. {article['title']}",
            "",
            f"- Source: {article['source']}",
            f"- Category: {article.get('source_category', '')}",
            f"- Type: {article.get('source_type', 'rss')}",
            f"- Web mode: {article.get('web_mode', '')}",
            f"- Published date: {article['published_date']}",
            f"- Freshness status: {article.get('freshness_status', 'unknown')}",
            f"- Content hash: {content_hash[:8]}",
            f"- First seen: {article.get('first_seen', '')}",
            f"- Last seen: {article.get('last_seen', '')}",
            f"- Seen count: {article.get('seen_count', 0)}",
            f"- URL: {article['url']}",
            f"- Score: {article['score']}",
            f"- Recommendation: {article['recommendation']}",
            "",
            "### Dimension Scores",
            "",
            f"- Relevance: {ranking['relevance']}/5",
            f"- Use Case Clarity: {ranking['use_case_clarity']}/5",
            f"- Problem-Solution Fit: {ranking['problem_solution_fit']}/5",
            f"- Actionability: {ranking['actionability']}/5",
            f"- Credibility & Novelty: {ranking['credibility_novelty']}/5",
            "",
            "### Use Case",
            "",
            ranking.get("use_case", ""),
            "",
            "### Problem Solved",
            "",
            ranking.get("problem_solved", ""),
            "",
            "### Reason",
            "",
            ranking.get("reason", ""),
            ""
        ])

    return "\n".join(lines)


def load_markdown(input_file):
    with input_file.open("r", encoding="utf-8") as file:
        return file.read()


def get_recommendation_from_section(section):
    for line in section.splitlines():
        if line.startswith("- Recommendation:"):
            return line.replace("- Recommendation:", "").strip()

    return ""


def filter_ranked_sources_for_analysis(ranked_sources):
    sections = []
    current_section = []

    for line in ranked_sources.splitlines():
        if line.startswith("## "):
            if current_section:
                sections.append("\n".join(current_section))
            current_section = [line]
        elif current_section:
            current_section.append(line)

    if current_section:
        sections.append("\n".join(current_section))

    primary_sections = []
    background_sections = []

    for section in sections:
        recommendation = get_recommendation_from_section(section)

        if recommendation in ["Core", "Useful"]:
            primary_sections.append(section)
        elif recommendation == "Background":
            background_sections.append(section)

    lines = [
        "# Ranked Sources for Market Analysis",
        "",
        "Use Core and Useful sources as primary evidence.",
        "Use Background sources only as supporting context.",
        "Prioritize sources whose Freshness status is new or updated.",
        "Use unknown freshness sources only as background, not as primary evidence for weekly trends.",
        "Do not use repeated or old sources as this week's market signal.",
        ""
    ]

    if primary_sections:
        lines.extend(primary_sections)

    if background_sections:
        lines.extend([
            "",
            "# Background Sources",
            ""
        ])
        lines.extend(background_sections)

    return "\n\n".join(lines)


def get_urls_from_markdown(markdown_text):
    urls = []

    for line in markdown_text.splitlines():
        if line.startswith("- URL:"):
            urls.append(line.replace("- URL:", "").strip())

    return urls


def get_reference_articles(ranked_articles):
    primary_articles = []
    background_articles = []

    for article in ranked_articles:
        if article["recommendation"] in ["Core", "Useful"]:
            primary_articles.append(article)
        elif article["recommendation"] == "Background":
            background_articles.append(article)

    return primary_articles + background_articles


def create_references_text(ranked_articles):
    reference_articles = get_reference_articles(ranked_articles)

    if not reference_articles:
        return "No Core, Useful, or Background sources were available."

    lines = []

    for index, article in enumerate(reference_articles, start=1):
        lines.extend([
            f"[來源 {index}] {article['title']}  ",
            f"- Source: {article['source']}",
            f"- Category: {article.get('source_category', '')}",
            f"- Type: {article.get('source_type', 'rss')}",
            f"- Web mode: {article.get('web_mode', '')}",
            f"- Published date: {article['published_date']}",
            f"- Freshness status: {article.get('freshness_status', 'unknown')}",
            f"- Recommendation: {article['recommendation']}",
            f"- URL: {article['url']}",
            ""
        ])

    return "\n".join(lines).strip()


def filter_market_brief_for_analysis(market_brief, allowed_urls):
    sections = []
    current_section = []

    for line in market_brief.splitlines():
        if line.startswith("## "):
            if current_section:
                sections.append("\n".join(current_section))
            current_section = [line]
        elif current_section:
            current_section.append(line)

    if current_section:
        sections.append("\n".join(current_section))

    lines = [
        f"# Market Brief for Analysis",
        "",
        f"Topic: {get_current_topic()}",
        ""
    ]

    for section in sections:
        section_urls = get_urls_from_markdown(section)

        if section_urls and section_urls[0] in allowed_urls:
            lines.append(section)

    if len(lines) == 4:
        lines.append("No Core, Useful, or Background articles were available.")

    return "\n\n".join(lines)


def ensure_report_has_references(report, references_text):
    reference_heading = "## 5. 參考資料"

    if reference_heading in report:
        report = report.split(reference_heading)[0].rstrip()

    return "\n".join([
        report.rstrip(),
        "",
        reference_heading,
        "",
        references_text,
        ""
    ])


def create_fallback_market_analysis_report(error, references_text):
    lines = [
        f"# Market Analysis Report: {get_current_topic()}",
        "",
        "## Fallback Report",
        "",
        f"- Topic: {get_current_topic()}",
        f"- Template: {REPORT_TEMPLATE}",
        f"- Error message: {error}",
        f"- Market brief path: {MARKET_BRIEF_FILE}",
        f"- Ranked sources path: {RANKED_SOURCES_FILE}",
        "",
        "## 5. 參考資料",
        ""
    ]

    if references_text:
        lines.append(references_text)
    else:
        lines.append("No references were available.")

    lines.append("")
    return "\n".join(lines)


def create_no_new_market_analysis_report(references_text):
    lines = [
        f"# Market Analysis Report: {get_current_topic()}",
        "",
        "## Fallback Report",
        "",
        "本週未觀察到足夠的新市場訊號，主要來源可能與過去重複，建議維持追蹤。",
        "",
        f"- Topic: {get_current_topic()}",
        f"- Template: {REPORT_TEMPLATE}",
        f"- Market brief path: {MARKET_BRIEF_FILE}",
        f"- Ranked sources path: {RANKED_SOURCES_FILE}",
        "",
        "## 5. 參考資料",
        ""
    ]

    if references_text:
        lines.append(references_text)
    else:
        lines.append("No references were available.")

    lines.append("")
    return "\n".join(lines)


def build_report_cache_entry(report, provider, cache_period):
    return {
        "topic": get_current_topic(),
        "report": report,
        "model": get_provider_model(provider),
        "cached_at": get_cached_at(),
        "cache_period": cache_period
    }


def get_report_from_cache(report_cache):
    cached_report = get_cached_result(report_cache, REPORT_TEMPLATE)

    if cached_report:
        return cached_report.get("report", "")

    return ""


def generate_market_analysis_report(provider, references_text):
    try:
        market_brief = load_markdown(MARKET_BRIEF_FILE)
        ranked_sources = load_markdown(RANKED_SOURCES_FILE)
        ranked_sources_for_analysis = filter_ranked_sources_for_analysis(
            ranked_sources
        )
        allowed_urls = get_urls_from_markdown(ranked_sources_for_analysis)
        market_brief_for_analysis = filter_market_brief_for_analysis(
            market_brief,
            allowed_urls
        )

        report = provider.generate_market_analysis_report(
            get_current_topic(),
            market_brief_for_analysis,
            ranked_sources_for_analysis,
            references_text
        )

        if not report.strip():
            raise ValueError("LLM returned an empty market analysis report.")

        return ensure_report_has_references(report, references_text), True
    except Exception as error:
        print(f"Warning: Could not generate market analysis report: {error}")
        return create_fallback_market_analysis_report(error, references_text), False


def get_market_analysis_report(
    provider,
    references_text,
    report_cache,
    report_cache_path,
    cache_period
):
    cached_report = get_report_from_cache(report_cache)

    if cached_report:
        print("Loaded market analysis report from cache.")
        return cached_report

    report, generated_successfully = generate_market_analysis_report(
        provider,
        references_text
    )

    if generated_successfully:
        cache_entry = build_report_cache_entry(report, provider, cache_period)
        set_cached_result(report_cache, REPORT_TEMPLATE, cache_entry)
        save_json_cache(report_cache_path, report_cache)
        print("Saved market analysis report to cache.")

    return report


def create_fallback_slide_draft(error):
    return "\n".join([
        f"# Slide Draft: {get_current_topic()}",
        "",
        "## Fallback Slide Draft",
        "",
        f"- Topic: {get_current_topic()}",
        f"- Error message: {error}",
        f"- Market analysis report path: {MARKET_ANALYSIS_REPORT_FILE}",
        "- Please review the market analysis report first, then regenerate the slide draft.",
        ""
    ])


def generate_slide_draft(provider):
    try:
        if not MARKET_ANALYSIS_REPORT_FILE.exists():
            raise FileNotFoundError(
                f"Market analysis report not found: {MARKET_ANALYSIS_REPORT_FILE}"
            )

        market_analysis_report = load_markdown(MARKET_ANALYSIS_REPORT_FILE)
        slide_draft = provider.generate_slide_draft(
            get_current_topic(),
            market_analysis_report
        )

        if not slide_draft.strip():
            raise ValueError("LLM returned an empty slide draft.")

        return slide_draft
    except Exception as error:
        print(f"Warning: Could not generate slide draft: {error}")
        return create_fallback_slide_draft(error)


def save_markdown(content, output_file):
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:
        file.write(content)


def main():
    global RUNTIME_TOPIC

    RUNTIME_TOPIC = get_resolved_topic()

    print("Market Intelligence Agent started.")
    print(f"Topic: {get_current_topic()}")

    keywords = load_keywords()
    articles, static_web_count, listing_web_count = fetch_articles_from_rss()
    relevant_articles = filter_articles_by_keywords(articles, keywords)
    save_articles(relevant_articles, RAW_OUTPUT_FILE)

    rss_article_count = len(articles) - static_web_count - listing_web_count

    print(f"Fetched {rss_article_count} articles from RSS sources.")
    print(f"Parsed {listing_web_count} listing web articles.")
    print(f"Added {static_web_count} static web sources.")
    print(f"Kept {len(relevant_articles)} relevant articles after keyword filtering.")
    print(f"Saved {len(relevant_articles)} articles to {RAW_OUTPUT_FILE}")

    raw_articles = load_articles(RAW_OUTPUT_FILE)
    clean_articles = extract_articles_content(raw_articles)
    clean_articles = enrich_articles_with_freshness(clean_articles)
    successful_extractions = 0

    for article in clean_articles:
        if article["extraction_status"] == "success":
            successful_extractions += 1

    save_articles(clean_articles, CLEAN_OUTPUT_FILE)
    print_freshness_summary(clean_articles)

    print(f"Extracted content for {successful_extractions}/{len(raw_articles)} articles.")
    print(f"Saved clean articles to {CLEAN_OUTPUT_FILE}")

    clean_articles = load_articles(CLEAN_OUTPUT_FILE)
    articles_ready_for_brief = get_articles_ready_for_brief(clean_articles)
    provider = get_llm_provider()
    week_key = get_current_week_key()
    cache_paths = get_cache_paths(get_current_topic(), week_key)
    summary_cache = load_json_cache(cache_paths["summary"])
    ranking_cache = load_json_cache(cache_paths["ranking"])
    report_cache = load_json_cache(cache_paths["report"])

    print(f"Using LLM provider: {LLM_PROVIDER}")
    print(f"Using summary cache: {cache_paths['summary']}")
    print(f"Using ranking cache: {cache_paths['ranking']}")
    print(f"Using report cache: {cache_paths['report']}")

    articles_for_llm = limit_articles_for_llm(articles_ready_for_brief)

    summarized_articles, successful_summaries = summarize_articles(
        articles_for_llm,
        provider,
        summary_cache,
        cache_paths["summary"],
        week_key
    )
    market_brief = create_market_brief(summarized_articles)
    save_markdown(market_brief, MARKET_BRIEF_FILE)

    print(f"Generated AI summaries for {successful_summaries} articles.")
    print(f"Saved market brief to {MARKET_BRIEF_FILE}")

    articles_ready_for_ranking = get_articles_ready_for_ranking(summarized_articles)
    ranked_articles = rank_articles(
        articles_ready_for_ranking,
        provider,
        ranking_cache,
        cache_paths["ranking"],
        week_key
    )
    ranked_sources_report = create_ranked_sources_report(ranked_articles)
    save_markdown(ranked_sources_report, RANKED_SOURCES_FILE)

    print(f"Ranked {len(ranked_articles)} articles by value.")
    print(f"Saved ranked sources to {RANKED_SOURCES_FILE}")

    references_text = create_references_text(ranked_articles)

    if articles_ready_for_brief:
        market_analysis_report = get_market_analysis_report(
            provider,
            references_text,
            report_cache,
            cache_paths["report"],
            week_key
        )
    else:
        market_analysis_report = create_no_new_market_analysis_report(
            references_text
        )

    save_markdown(market_analysis_report, MARKET_ANALYSIS_REPORT_FILE)

    print("Generated market analysis report with references.")
    print(f"Saved market analysis report to {MARKET_ANALYSIS_REPORT_FILE}")

    if SLIDE_DRAFT_ENABLED:
        slide_draft = generate_slide_draft(provider)
        save_markdown(slide_draft, SLIDE_DRAFT_FILE)

        print("Generated slide draft.")
        print(f"Saved slide draft to {SLIDE_DRAFT_FILE}")


if __name__ == "__main__":
    main()
