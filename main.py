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
    LLM_MODEL,
    LLM_PROVIDER,
    REPORT_TEMPLATE,
    RSS_SOURCES
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

RAW_OUTPUT_FILE = Path("data/raw_articles/articles.json")
CLEAN_OUTPUT_FILE = Path("data/clean_articles/clean_articles.json")
MARKET_BRIEF_FILE = Path("outputs/reports/market_brief.md")
RANKED_SOURCES_FILE = Path("outputs/reports/ranked_sources.md")
MARKET_ANALYSIS_REPORT_FILE = Path("outputs/reports/market_analysis_report.md")
KEYWORDS_FILE = Path("config/keywords.json")
ARTICLES_PER_SOURCE = 5
MAX_SCORE = 37.5


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
        "published_date": article["published_date"],
        "topic": article["topic"],
        "model": get_provider_model(provider),
        "summary": ai_summary.get("summary", ""),
        "key_points": ai_summary.get("key_points", []),
        "why_it_matters": ai_summary.get("why_it_matters", ""),
        "cached_at": get_cached_at(),
        "cache_period": cache_period
    }


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

        if cached_summary:
            ai_summary = get_summary_from_cache(cached_summary)
            print(f"Loaded summary from cache for: {article['title']}")
        else:
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
        "published_date": article["published_date"],
        "topic": article["topic"],
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

        if cached_ranking:
            ranking = get_ranking_from_cache(cached_ranking)
            score = cached_ranking.get("score", 55.0)
            recommendation = cached_ranking.get("recommendation", "Background")
            print(f"Loaded ranking from cache for: {article['title']}")
        else:
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


def create_ranked_sources_report(articles):
    lines = [
        "# Ranked Sources",
        "",
        f"Topic: {DEFAULT_TOPIC}",
        "",
        f"Articles evaluated: {len(articles)}",
        ""
    ]

    for index, article in enumerate(articles, start=1):
        ranking = article["ranking"]

        lines.extend([
            f"## {index}. {article['title']}",
            "",
            f"- Source: {article['source']}",
            f"- Published date: {article['published_date']}",
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
        f"Topic: {DEFAULT_TOPIC}",
        ""
    ]

    for section in sections:
        section_urls = get_urls_from_markdown(section)

        if section_urls and section_urls[0] in allowed_urls:
            lines.append(section)

    if len(lines) == 4:
        lines.append("No Core, Useful, or Background articles were available.")

    return "\n\n".join(lines)


def create_fallback_market_analysis_report(error):
    return "\n".join([
        f"# Market Analysis Report: {DEFAULT_TOPIC}",
        "",
        "## Fallback Report",
        "",
        f"- Topic: {DEFAULT_TOPIC}",
        f"- Template: {REPORT_TEMPLATE}",
        f"- Error message: {error}",
        f"- Market brief path: {MARKET_BRIEF_FILE}",
        f"- Ranked sources path: {RANKED_SOURCES_FILE}",
        ""
    ])


def generate_market_analysis_report(provider):
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
            DEFAULT_TOPIC,
            market_brief_for_analysis,
            ranked_sources_for_analysis
        )

        if not report.strip():
            raise ValueError("LLM returned an empty market analysis report.")

        return report
    except Exception as error:
        print(f"Warning: Could not generate market analysis report: {error}")
        return create_fallback_market_analysis_report(error)


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
    week_key = get_current_week_key()
    cache_paths = get_cache_paths(DEFAULT_TOPIC, week_key)
    summary_cache = load_json_cache(cache_paths["summary"])
    ranking_cache = load_json_cache(cache_paths["ranking"])

    print(f"Using LLM provider: {LLM_PROVIDER}")
    print(f"Using summary cache: {cache_paths['summary']}")
    print(f"Using ranking cache: {cache_paths['ranking']}")

    summarized_articles, successful_summaries = summarize_articles(
        articles_ready_for_brief,
        provider,
        summary_cache,
        cache_paths["summary"],
        week_key
    )
    market_brief = create_market_brief(summarized_articles)
    save_markdown(market_brief, MARKET_BRIEF_FILE)

    print(f"Generated AI summaries for {successful_summaries} articles.")
    print(f"Saved market brief to {MARKET_BRIEF_FILE}")

    ranked_articles = rank_articles(
        articles_ready_for_brief,
        provider,
        ranking_cache,
        cache_paths["ranking"],
        week_key
    )
    ranked_sources_report = create_ranked_sources_report(ranked_articles)
    save_markdown(ranked_sources_report, RANKED_SOURCES_FILE)

    print(f"Ranked {len(ranked_articles)} articles by value.")
    print(f"Saved ranked sources to {RANKED_SOURCES_FILE}")

    market_analysis_report = generate_market_analysis_report(provider)
    save_markdown(market_analysis_report, MARKET_ANALYSIS_REPORT_FILE)

    print("Generated market analysis report.")
    print(f"Saved market analysis report to {MARKET_ANALYSIS_REPORT_FILE}")


if __name__ == "__main__":
    main()
