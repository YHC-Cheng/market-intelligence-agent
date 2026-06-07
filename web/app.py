import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode, urlsplit

from config import RSS_SOURCES_BY_TOPIC, SOURCES
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.repositories.json_knowledge_repository import JsonKnowledgeRepository
from web.repositories.json_weekly_report_snapshot_repository import (
    JsonWeeklyReportSnapshotRepository,
)
from web.services.article_processing import ArticleProcessingService
from web.services.report_re_export import build_report_re_export_markdown
from web.services.weekly_report_snapshot_writer import WeeklyReportSnapshotWriter


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
NEWSLETTER_OUTPUT_DIR = REPO_ROOT / "outputs" / "newsletter"
KEYWORDS_CONFIG_PATH = REPO_ROOT / "config" / "keywords.json"
REPORT_OUTPUT_FILES_ROOT = REPO_ROOT / "outputs" / "runs"

app = FastAPI(title="Market Intelligence Agent 2.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

NAVIGATION_ITEMS = [
    {"key": "home", "label": "Dashboard", "href": "/"},
    {"key": "newsletter", "label": "Weekly Brief", "href": "/newsletter"},
    {"key": "reports", "label": "Reports", "href": "/reports"},
    {"key": "reference", "label": "Reference", "href": "/reference"},
]

INTAKE_TOPIC_OPTIONS = [
    "AI",
    "FinOps",
    "ProductObservation",
]

REVIEW_STATUS_OPTIONS = [
    "unreviewed",
    "approved",
    "rejected",
    "needs_fix",
    "duplicate",
]

REVIEW_QUEUE_STATUSES = {
    "unreviewed",
    "needs_fix",
    "duplicate",
}

REVIEW_ACTION_STATUS_UPDATES = {
    "approve": "approved",
    "reject": "rejected",
    "mark_duplicate": "duplicate",
}

NEWSLETTER_TOPIC_OPTIONS = INTAKE_TOPIC_OPTIONS
ARTICLES_PER_PAGE = 15
SUMMARY_STATUS_TABS = [
    {"value": "ready", "label": "Ready"},
    {"value": "needs_attention", "label": "Needs Attention"},
    {"value": "failed", "label": "Failed"},
    {"value": "to_extract", "label": "To Extract"},
    {"value": "skipped", "label": "Skipped"},
    {"value": "all", "label": "All"},
]
SUMMARY_STATUS_FILTERS = {tab["value"] for tab in SUMMARY_STATUS_TABS}
DEFAULT_SUMMARY_STATUS_FILTER = "ready"
RECOMMENDATION_OPTIONS = ["Core", "Useful", "Exclude"]
WEEKLY_BRIEF_RECOMMENDATIONS = {"Core", "Useful"}
WEEKLY_BRIEF_TOTAL_LIMIT = 10
WEEKLY_BRIEF_TOPIC_LIMIT = 3
RETRYABLE_FAILURE_REASONS = {
    "fetch_failed",
    "http_error",
    "extraction_failed",
    "llm_summary_failed",
    "repository_write_failed",
    "unknown_error",
}


def get_knowledge_repository():
    return JsonKnowledgeRepository()


def get_report_snapshot_repository():
    return JsonWeeklyReportSnapshotRepository()


def get_report_snapshot_writer():
    return WeeklyReportSnapshotWriter(
        repository=get_report_snapshot_repository(),
    )


def get_article_processing_service(repository=None):
    return ArticleProcessingService(repository or get_knowledge_repository())


def base_template_context(
    request: Request,
    title,
    active_nav=None,
    page_title=None,
    page_subtitle=None,
    page_action_label=None,
    page_action_href=None,
    show_page_header=True,
):
    return {
        "request": request,
        "title": title,
        "navigation_items": NAVIGATION_ITEMS,
        "active_nav": active_nav,
        "page_title": page_title or title,
        "page_subtitle": page_subtitle,
        "page_action_label": page_action_label,
        "page_action_href": page_action_href,
        "show_page_header": show_page_header,
    }


def clean_filter(value):
    if value is None:
        return None

    cleaned_value = value.strip()
    return cleaned_value or None


def parse_bool_filter(value):
    cleaned_value = clean_filter(value)
    if cleaned_value is None:
        return None

    normalized_value = cleaned_value.casefold()
    if normalized_value in {"1", "true", "yes", "on"}:
        return True
    if normalized_value in {"0", "false", "no", "off"}:
        return False

    return None


def normalize_summary_status_filter(value):
    normalized_value = clean_filter(value)
    if normalized_value is None:
        return DEFAULT_SUMMARY_STATUS_FILTER

    normalized_value = normalized_value.casefold()
    if normalized_value == "needs_summary":
        return "to_extract"

    if normalized_value in SUMMARY_STATUS_FILTERS:
        return normalized_value

    return DEFAULT_SUMMARY_STATUS_FILTER


def article_detail_href(article):
    article_id = (
        article.get("id")
        or article.get("canonical_url")
        or article.get("url")
        or ""
    )
    return f"/articles/{quote(str(article_id), safe='')}"


def with_detail_hrefs(articles):
    article_list = []
    for article in articles:
        article_copy = dict(article)
        article_copy["detail_href"] = article_detail_href(article_copy)
        article_list.append(article_copy)

    return article_list


def article_filters(
    topic=None,
    keyword=None,
    review_status=None,
    newsletter_eligible=None,
    source=None,
    article_type=None,
    summary_status=None,
    recommendation=None,
):
    return {
        "topic": clean_filter(topic),
        "keyword": clean_filter(keyword),
        "review_status": clean_filter(review_status),
        "newsletter_eligible": clean_filter(newsletter_eligible),
        "source": clean_filter(source),
        "article_type": clean_filter(article_type),
        "summary_status": normalize_summary_status_filter(summary_status),
        "recommendation": clean_filter(recommendation),
    }


def article_type(article):
    return article.get("ingestion_type") or article.get("type")


def normalize_summary_status(article):
    summary_status = str(article.get("summary_status") or "").strip().casefold()
    if summary_status == "ready":
        return "ready"
    if summary_status == "failed":
        return "failed"
    if summary_status in {"to_extract", "needs_summary"}:
        return "to_extract"
    if summary_status in {"skipped", "not_selected", "metadata_only", "archived"}:
        return "skipped"

    if article_has_summary(article):
        return "ready"

    if article_is_failed(article):
        return "failed"

    if article_is_skipped_metadata(article):
        return "skipped"

    if article_is_manual(article):
        return "to_extract"

    analysis_status = str(article.get("analysis_status") or "").strip().casefold()
    if analysis_status in {"not_started", "pending"}:
        return "to_extract"

    return "to_extract"


def article_summary_status_bucket(article):
    return normalize_summary_status(article)


def display_summary_status(article):
    bucket = article_summary_status_bucket(article)
    if bucket == "ready":
        return "Ready"
    if bucket == "failed":
        return "Failed"
    if bucket == "skipped":
        return "Skipped"

    return "To Extract"


def summary_status_explanation(article):
    bucket = article_summary_status_bucket(article)
    if bucket == "ready":
        return "Summary is available for this article."
    if bucket == "failed":
        return "Summary generation failed. You can try generating it again."
    if bucket == "skipped":
        return "This pipeline article was not selected for summary generation."

    return "This article has not been summarized yet."


def can_generate_summary(article):
    return article_summary_status_bucket(article) == "to_extract"


def is_retryable_failure_reason(failure_reason):
    return failure_reason in RETRYABLE_FAILURE_REASONS


def is_retryable_failure(article):
    if article_summary_status_bucket(article) != "failed":
        return False

    return is_retryable_failure_reason(article.get("failure_reason"))


def updated_date(article):
    updated_at = article.get("updated_at")
    if updated_at in (None, ""):
        return None

    try:
        parsed_date = datetime.fromisoformat(str(updated_at).replace("Z", "+00:00"))
    except ValueError:
        return None

    return parsed_date.date().isoformat()


def with_home_article_fields(articles):
    article_list = []
    for article in with_detail_hrefs(articles):
        article_copy = dict(article)
        article_copy["summary_status_display"] = display_summary_status(article_copy)
        article_copy["summary_status_bucket"] = article_summary_status_bucket(article_copy)
        article_copy["updated_date"] = updated_date(article_copy)
        article_list.append(article_copy)

    return article_list


def parse_page(value):
    try:
        page = int(value)
    except (TypeError, ValueError):
        return 1

    if page < 1:
        return 1

    return page


def pagination_href(page, filters):
    query_params = []
    for query_name, filter_name in [
        ("keyword", "keyword"),
        ("topic", "topic"),
        ("summary_status", "summary_status"),
        ("recommendation", "recommendation"),
    ]:
        if filters.get(filter_name):
            query_params.append((query_name, filters[filter_name]))

    query_params.append(("page", page))
    return f"/?{urlencode(query_params)}"


def summary_status_tab_href(filters, summary_status):
    query_params = [("summary_status", summary_status)]
    for query_name, filter_name in [
        ("keyword", "keyword"),
        ("topic", "topic"),
        ("recommendation", "recommendation"),
    ]:
        if filters.get(filter_name):
            query_params.append((query_name, filters[filter_name]))

    return f"/?{urlencode(query_params)}"


def summary_status_tabs(filters):
    return [
        {
            **tab,
            "href": summary_status_tab_href(filters, tab["value"]),
            "active": filters["summary_status"] == tab["value"],
        }
        for tab in SUMMARY_STATUS_TABS
    ]


def paginate_articles(articles, page, filters):
    total_count = len(articles)
    total_pages = max(1, (total_count + ARTICLES_PER_PAGE - 1) // ARTICLES_PER_PAGE)
    current_page = min(parse_page(page), total_pages)
    start_index = (current_page - 1) * ARTICLES_PER_PAGE
    end_index = min(start_index + ARTICLES_PER_PAGE, total_count)

    return {
        "articles": articles[start_index:end_index],
        "page": current_page,
        "total_pages": total_pages,
        "total_count": total_count,
        "display_start": start_index + 1 if total_count else 0,
        "display_end": end_index,
        "has_previous": current_page > 1,
        "has_next": current_page < total_pages,
        "previous_href": pagination_href(current_page - 1, filters)
        if current_page > 1
        else None,
        "next_href": pagination_href(current_page + 1, filters)
        if current_page < total_pages
        else None,
    }


def apply_home_filters(articles, filters):
    filtered_articles = articles

    if filters["source"] is not None:
        filtered_articles = [
            article
            for article in filtered_articles
            if article.get("source") == filters["source"]
        ]

    if filters["article_type"] is not None:
        filtered_articles = [
            article
            for article in filtered_articles
            if article_type(article) == filters["article_type"]
        ]

    if filters["summary_status"] == "ready":
        filtered_articles = [
            article
            for article in filtered_articles
            if article_summary_status_bucket(article) == "ready"
        ]
    elif filters["summary_status"] == "failed":
        filtered_articles = [
            article
            for article in filtered_articles
            if article_summary_status_bucket(article) == "failed"
        ]
    elif filters["summary_status"] == "to_extract":
        filtered_articles = [
            article
            for article in filtered_articles
            if article_summary_status_bucket(article) == "to_extract"
        ]
    elif filters["summary_status"] == "skipped":
        filtered_articles = [
            article
            for article in filtered_articles
            if article_summary_status_bucket(article) == "skipped"
        ]
    elif filters["summary_status"] == "needs_attention":
        filtered_articles = [
            article
            for article in filtered_articles
            if article_needs_attention(article)
        ]

    if filters["recommendation"] is not None:
        filtered_articles = [
            article
            for article in filtered_articles
            if article.get("recommendation") == filters["recommendation"]
        ]

    return filtered_articles


def option_values(articles, field):
    values = {
        article.get(field)
        for article in articles
        if article.get(field) not in (None, "")
    }
    return sorted(values)


def type_option_values(articles):
    values = {
        article_type(article)
        for article in articles
        if article_type(article) not in (None, "")
    }
    return sorted(values)


def article_score(article):
    score = article.get("score")
    if score is None:
        score = article.get("ranking_score")

    try:
        return float(score)
    except (TypeError, ValueError):
        return -1


def brief_signal_articles(articles):
    candidates = [
        article
        for article in articles
        if article.get("title") or article.get("recommendation")
    ]
    return sorted(
        candidates,
        key=lambda article: (
            article_score(article),
            1 if article.get("recommendation") else 0,
        ),
        reverse=True,
    )[:4]


def recommendation_rank(article):
    recommendation = article.get("recommendation")
    if recommendation == "Core":
        return 3
    if recommendation == "Useful":
        return 2
    return 0


def article_has_summary(article):
    return bool(str(article.get("summary") or "").strip())


def article_is_manual(article):
    return (
        article.get("source") == "manual"
        or article.get("source_type") == "manual"
        or article.get("ingestion_type") == "manual"
    )


def article_is_failed(article):
    extraction_status = str(
        article.get("extraction_status") or ""
    ).strip().casefold()
    analysis_status = str(article.get("analysis_status") or "").strip().casefold()
    if extraction_status in {"failed", "error"}:
        return True
    if analysis_status in {"failed", "error"}:
        return True

    return bool(article.get("failure_reason"))


def article_is_skipped_metadata(article):
    freshness_status = str(
        article.get("freshness_status") or ""
    ).strip().casefold()
    if freshness_status in {"old", "repeated"}:
        return True

    if str(article.get("llm_status") or "").strip().casefold() in {
        "skipped",
        "not_selected",
    }:
        return True

    if str(article.get("processing_status") or "").strip().casefold() in {
        "skipped",
        "not_selected",
        "metadata_only",
    }:
        return True

    return False


def article_needs_attention(article):
    summary_status = article_summary_status_bucket(article)
    if summary_status == "skipped":
        return False

    if summary_status in {"failed", "to_extract"}:
        return True

    recommendation = article.get("recommendation")
    if recommendation is None or str(recommendation).strip() == "":
        return True

    if recommendation == "Background":
        return True

    if summary_status == "ready" and not article_has_summary(article):
        return True

    return False


def is_weekly_brief_candidate(article):
    return (
        article_summary_status_bucket(article) == "ready"
        and article.get("recommendation") in WEEKLY_BRIEF_RECOMMENDATIONS
        and article_has_summary(article)
    )


def article_processed_timestamp(article):
    processed_at = article.get("last_processed_at")
    if processed_at in (None, ""):
        return 0.0

    try:
        return datetime.fromisoformat(
            str(processed_at).replace("Z", "+00:00"),
        ).timestamp()
    except (TypeError, ValueError):
        return 0.0


def article_ranking_score(article):
    try:
        return float(article.get("ranking_score"))
    except (TypeError, ValueError):
        return -1


def weekly_brief_sort_key(article):
    return (
        recommendation_rank(article),
        article_processed_timestamp(article),
        article_ranking_score(article),
    )


def weekly_brief_candidate_articles(topic=None):
    repository = get_knowledge_repository()
    articles = repository.list_articles(topic=topic)

    eligible_articles = [
        article
        for article in articles
        if is_weekly_brief_candidate(article)
    ]

    sorted_candidates = sorted(
        eligible_articles,
        key=weekly_brief_sort_key,
        reverse=True,
    )

    limited_candidates = []
    topic_counts = {}
    for article in sorted_candidates:
        topic_name = article.get("topic") or ""
        topic_count = topic_counts.get(topic_name, 0)
        if topic_count >= WEEKLY_BRIEF_TOPIC_LIMIT:
            continue

        limited_candidates.append(article)
        topic_counts[topic_name] = topic_count + 1

        if len(limited_candidates) >= WEEKLY_BRIEF_TOTAL_LIMIT:
            break

    return with_detail_hrefs(limited_candidates)


def current_week_label(generated_at=None):
    today = (generated_at or datetime.now()).date()
    week_start = today.fromordinal(today.toordinal() - today.weekday())
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    return (
        f"{week_start:%b} {week_start.day} - "
        f"{week_end:%b} {week_end.day}, {week_end.year}"
    )


def home_articles_context(
    request: Request,
    topic=None,
    keyword=None,
    review_status=None,
    newsletter_eligible=None,
    source=None,
    article_type_filter=None,
    summary_status=None,
    recommendation=None,
    page=None,
):
    filters = article_filters(
        topic=topic,
        keyword=keyword,
        review_status=review_status,
        newsletter_eligible=newsletter_eligible,
        source=source,
        article_type=article_type_filter,
        summary_status=summary_status,
        recommendation=recommendation,
    )
    repository = get_knowledge_repository()
    repository_articles = repository.list_articles(
        topic=filters["topic"],
        keyword=filters["keyword"],
        review_status=filters["review_status"],
        newsletter_eligible=parse_bool_filter(filters["newsletter_eligible"]),
    )
    filtered_articles = apply_home_filters(repository_articles, filters)
    pagination = paginate_articles(filtered_articles, page, filters)
    all_articles = repository.list_articles()
    topic_counts = {}
    for article in all_articles:
        topic_name = article.get("topic")
        if topic_name:
            topic_counts[topic_name] = topic_counts.get(topic_name, 0) + 1

    context = base_template_context(
        request,
        title="Dashboard",
        active_nav="home",
        page_title="Dashboard",
        page_subtitle="Track this week's market intelligence and articles.",
        page_action_label="Add Article",
        page_action_href="/intake",
    )
    context.update(
        {
            "articles": with_home_article_fields(pagination["articles"]),
            "filters": filters,
            "pagination": pagination,
            "summary_status_tabs": summary_status_tabs(filters),
            "topic_options": option_values(all_articles, "topic"),
            "recommendation_options": option_values(
                all_articles,
                "recommendation",
            ),
            "brief_signal_articles": with_detail_hrefs(
                brief_signal_articles(filtered_articles)
            ),
            "article_summary": {
                "total": len(all_articles),
                "shown": len(filtered_articles),
                "manual": sum(
                    1
                    for article in all_articles
                    if article_type(article) == "manual"
                ),
                "date_range": current_week_label(),
                "topics": topic_counts,
            },
        }
    )
    return context


@app.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    topic: Optional[str] = None,
    keyword: Optional[str] = None,
    review_status: Optional[str] = None,
    newsletter_eligible: Optional[str] = Query(default=None),
    source: Optional[str] = None,
    article_type_filter: Optional[str] = Query(default=None, alias="type"),
    summary_status: Optional[str] = None,
    status: Optional[str] = None,
    recommendation: Optional[str] = None,
    page: Optional[str] = None,
):
    selected_summary_status = summary_status or status
    return templates.TemplateResponse(
        request,
        "index.html",
        home_articles_context(
            request,
            topic=topic,
            keyword=keyword,
            review_status=review_status,
            newsletter_eligible=newsletter_eligible,
            source=source,
            article_type_filter=article_type_filter,
            summary_status=selected_summary_status,
            recommendation=recommendation,
            page=page,
        ),
    )


def intake_context(
    request: Request,
    form=None,
    error=None,
    duplicate_article=None,
):
    duplicate_detail_href = None
    if duplicate_article is not None:
        duplicate_detail_href = article_detail_href(duplicate_article)

    context = home_articles_context(request)
    context.update(
        base_template_context(
            request,
            title="Add Article",
            active_nav="home",
            page_title="Add Article",
            page_subtitle="Add a market intelligence article URL.",
            show_page_header=False,
        )
    )
    context.update(
        {
            "intake_topic_options": INTAKE_TOPIC_OPTIONS,
            "form": form or {"url": "", "topic": "", "note": ""},
            "error": error,
            "duplicate_article": duplicate_article,
            "duplicate_detail_href": duplicate_detail_href,
        }
    )
    return context


def normalize_manual_article_url(url):
    cleaned_url = clean_filter(url)
    if cleaned_url is None:
        return None, "URL is required."

    try:
        parsed_url = urlsplit(cleaned_url)
        parsed_url.port
    except ValueError:
        return None, "Enter a valid http or https URL."

    if parsed_url.scheme.lower() not in {"http", "https"}:
        return None, "Enter a valid http or https URL."

    if not parsed_url.netloc or parsed_url.hostname is None:
        return None, "Enter a valid http or https URL."

    return JsonKnowledgeRepository.normalize_url(cleaned_url), None


def review_queue_url(topic=None, message=None, error=None):
    params = {}
    if topic:
        params["topic"] = topic
    if message:
        params["message"] = message
    if error:
        params["error"] = error

    if not params:
        return "/review"

    return f"/review?{urlencode(params)}"


def review_queue_articles(topic=None):
    repository = get_knowledge_repository()
    articles = repository.list_articles(topic=topic)
    queue_articles = [
        article
        for article in articles
        if article.get("review_status") in REVIEW_QUEUE_STATUSES
    ]
    return with_detail_hrefs(queue_articles)


def normalize_newsletter_topic(topic=None):
    selected_topic = clean_filter(topic)
    if selected_topic in NEWSLETTER_TOPIC_OPTIONS:
        return selected_topic

    return None


def newsletter_articles(topic=None):
    return weekly_brief_candidate_articles(topic=topic)


def newsletter_filename_topic(topic=None):
    if not topic:
        return "all"

    return "".join(
        character.lower()
        for character in topic
        if character.isalnum() or character in {"-", "_"}
    ) or "all"


def markdown_value(value):
    return str(value).strip() if value not in (None, "") else "-"


def newsletter_markdown(articles, topic=None, generated_at=None):
    generated_timestamp = generated_at or datetime.now().replace(
        microsecond=0,
    ).isoformat()
    topic_label = topic or "Any"
    lines = [
        "# Weekly Brief",
        "",
        f"- topic: {topic_label}",
        f"- generated_at: {generated_timestamp}",
        f"- article_count: {len(articles)}",
        "",
    ]

    if not articles:
        lines.extend(
            [
                "No high-signal articles available for this week yet.",
                "",
            ]
        )

    for index, article in enumerate(articles, start=1):
        lines.extend(
            [
                f"## {index}. {markdown_value(article.get('title'))}",
                "",
                f"- source: {markdown_value(article.get('source'))}",
                f"- url: {markdown_value(article.get('url'))}",
                f"- recommendation: {markdown_value(article.get('recommendation'))}",
                f"- score: {markdown_value(article.get('score') or article.get('ranking_score'))}",
                "",
                f"**Summary:** {markdown_value(article.get('summary'))}",
                "",
                f"**Use case:** {markdown_value(article.get('use_case'))}",
                "",
                "**Problem solved:** "
                f"{markdown_value(article.get('problem_solved'))}",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def newsletter_output_path(topic=None):
    filename_topic = newsletter_filename_topic(topic)
    return NEWSLETTER_OUTPUT_DIR / f"weekly_brief_{filename_topic}.md"


def current_weekly_brief_item(topic=None):
    articles = newsletter_articles(topic=topic)
    article_count = len(articles)
    return {
        "title": "Current Weekly Brief",
        "href": "/newsletter/current",
        "date_range": current_week_label(),
        "article_count": article_count,
        "article_count_display": (
            f"{article_count} high-signal article"
            f"{'' if article_count == 1 else 's'}"
        ),
        "status": "Current",
        "updated": datetime.now().date().isoformat(),
    }


def reference_keywords():
    try:
        with KEYWORDS_CONFIG_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, dict):
        return []

    keyword_groups = []
    for topic, keywords in sorted(data.items()):
        if not isinstance(keywords, list):
            continue

        clean_keywords = [
            str(keyword)
            for keyword in keywords
            if keyword not in (None, "")
        ]
        keyword_groups.append({"topic": str(topic), "keywords": clean_keywords})

    return keyword_groups


def reference_sources():
    sources = []
    seen = set()

    for topic, topic_sources in RSS_SOURCES_BY_TOPIC.items():
        for source in topic_sources:
            if not isinstance(source, dict):
                continue
            name = source.get("name")
            url = source.get("url")
            source_type = source.get("type") or source.get("web_mode")
            key = (name, topic, source_type, url)
            if key in seen:
                continue
            seen.add(key)
            sources.append(
                {
                    "name": name or "-",
                    "topic": topic,
                    "type": source_type,
                    "url": url,
                }
            )

    for source in SOURCES:
        if not isinstance(source, dict):
            continue
        name = source.get("name")
        url = source.get("url")
        key = (name, "General", "web", url)
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "name": name or "-",
                "topic": "General",
                "type": "web",
                "url": url,
            }
        )

    return sources


@app.get("/articles", response_class=HTMLResponse)
async def articles(request: Request):
    query_string = request.scope.get("query_string", b"").decode("latin-1")
    redirect_url = f"/?{query_string}" if query_string else "/"
    return RedirectResponse(url=redirect_url, status_code=307)


@app.get("/reference", response_class=HTMLResponse)
async def reference(request: Request):
    context = base_template_context(
        request,
        title="Reference",
        active_nav="reference",
        page_title="Reference",
        page_subtitle="View workflow keywords and source links.",
    )
    context.update(
        {
            "keyword_groups": reference_keywords(),
            "source_links": reference_sources(),
        }
    )
    return templates.TemplateResponse(request, "reference.html", context)


@app.get("/reports", response_class=HTMLResponse)
async def reports(
    request: Request,
    backfill_scanned_count: Optional[int] = None,
    backfill_created_or_updated_count: Optional[int] = None,
    backfill_skipped_count: Optional[int] = None,
    backfill_error_count: Optional[int] = None,
):
    repository = get_report_snapshot_repository()
    snapshots = [
        {
            **snapshot,
            "detail_href": (
                f"/reports/{quote(str(snapshot.get('snapshot_id', '')), safe='')}"
            ),
        }
        for snapshot in repository.list_snapshots(report_type="weekly")
    ]

    return templates.TemplateResponse(
        request,
        "reports.html",
        {
            **base_template_context(
                request,
                title="Reports",
                active_nav="reports",
                page_title="Report History",
                page_subtitle="Browse saved weekly report snapshots.",
            ),
            "snapshots": snapshots,
            "backfill_result": report_backfill_result_context(
                backfill_scanned_count,
                backfill_created_or_updated_count,
                backfill_skipped_count,
                backfill_error_count,
            ),
        },
    )


def report_backfill_result_context(
    scanned_count=None,
    created_or_updated_count=None,
    skipped_count=None,
    error_count=None,
):
    if scanned_count is None:
        return None

    return {
        "scanned_count": scanned_count or 0,
        "created_or_updated_count": created_or_updated_count or 0,
        "skipped_count": skipped_count or 0,
        "error_count": error_count or 0,
    }


@app.post("/reports/backfill")
async def backfill_reports():
    result = get_report_snapshot_writer().backfill_snapshots_from_runs()
    params = {
        "backfill_scanned_count": result.get("scanned_count", 0),
        "backfill_created_or_updated_count": result.get(
            "created_or_updated_count",
            0,
        ),
        "backfill_skipped_count": result.get("skipped_count", 0),
        "backfill_error_count": result.get("error_count", 0),
    }
    return RedirectResponse(
        url=f"/reports?{urlencode(params)}",
        status_code=303,
    )


def report_file_label(file_key):
    return str(file_key).replace("_", " ").title()


def report_file_href(snapshot_id, file_key, download=False):
    href = (
        f"/reports/{quote(str(snapshot_id), safe='')}"
        f"/files/{quote(str(file_key), safe='')}"
    )
    if download:
        return f"{href}/download"

    return href


def report_re_export_href(snapshot_id):
    return (
        f"/reports/{quote(str(snapshot_id), safe='')}"
        "/re-export/download"
    )


def with_report_file_actions(snapshot):
    snapshot_copy = dict(snapshot)
    snapshot_id = snapshot_copy.get("snapshot_id", "")
    files = {}

    for file_key, file_metadata in (snapshot_copy.get("files") or {}).items():
        file_copy = dict(file_metadata) if isinstance(file_metadata, dict) else {}
        file_copy["label"] = report_file_label(file_key)

        if file_copy.get("status") == "available":
            file_copy["view_href"] = report_file_href(snapshot_id, file_key)
            file_copy["download_href"] = report_file_href(
                snapshot_id,
                file_key,
                download=True,
            )

        files[file_key] = file_copy

    snapshot_copy["files"] = files
    return snapshot_copy


def get_report_snapshot_or_404(snapshot_id):
    repository = get_report_snapshot_repository()
    snapshot = repository.get_snapshot(snapshot_id)

    if snapshot is None:
        raise HTTPException(status_code=404, detail="Report snapshot not found")

    return snapshot


def get_report_file_metadata_or_404(snapshot, file_key):
    files = snapshot.get("files") or {}
    file_metadata = files.get(file_key)

    if not isinstance(file_metadata, dict):
        raise HTTPException(status_code=404, detail="Report file not found")

    if file_metadata.get("status") != "available":
        raise HTTPException(status_code=404, detail="Report file is not available")

    return file_metadata


def resolve_report_output_file_path_or_404(file_metadata):
    file_path = file_metadata.get("path")
    if not file_path:
        raise HTTPException(status_code=404, detail="Report file path not found")

    candidate_path = Path(file_path)
    if not candidate_path.is_absolute():
        candidate_path = REPO_ROOT / candidate_path

    try:
        resolved_path = candidate_path.resolve(strict=False)
        allowed_root = REPORT_OUTPUT_FILES_ROOT.resolve(strict=False)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail="Report file not found")

    try:
        resolved_path.relative_to(allowed_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Report file not found")

    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Report file not found")

    return resolved_path


def get_report_file_or_404(snapshot_id, file_key):
    snapshot = get_report_snapshot_or_404(snapshot_id)
    file_metadata = get_report_file_metadata_or_404(snapshot, file_key)
    file_path = resolve_report_output_file_path_or_404(file_metadata)

    return snapshot, file_metadata, file_path


def read_report_file_content_for_re_export(snapshot, file_key):
    file_metadata = get_report_file_metadata_or_404(snapshot, file_key)
    file_path = resolve_report_output_file_path_or_404(file_metadata)
    return file_path.read_text(encoding="utf-8", errors="replace")


def report_export_filename(snapshot_id):
    cleaned = "".join(
        character if character.isalnum() or character in {"-", "_", "."} else "_"
        for character in str(snapshot_id)
    )
    return f"report_export_{cleaned or 'snapshot'}.md"


@app.get("/reports/{snapshot_id}", response_class=HTMLResponse)
async def report_detail(request: Request, snapshot_id: str):
    snapshot = with_report_file_actions(get_report_snapshot_or_404(snapshot_id))

    return templates.TemplateResponse(
        request,
        "report_detail.html",
        {
            **base_template_context(
                request,
                title=snapshot.get("title") or "Report Detail",
                active_nav="reports",
                page_title=snapshot.get("title") or "Report Detail",
                page_subtitle="Weekly report snapshot metadata.",
            ),
            "snapshot": snapshot,
            "re_export_href": report_re_export_href(
                snapshot.get("snapshot_id", snapshot_id)
            ),
        },
    )


@app.get("/reports/{snapshot_id}/files/{file_key}", response_class=HTMLResponse)
async def report_file(request: Request, snapshot_id: str, file_key: str):
    snapshot, file_metadata, file_path = get_report_file_or_404(
        snapshot_id,
        file_key,
    )
    file_content = file_path.read_text(encoding="utf-8", errors="replace")

    return templates.TemplateResponse(
        request,
        "report_file.html",
        {
            **base_template_context(
                request,
                title=f"{report_file_label(file_key)} - Report File",
                active_nav="reports",
                page_title=report_file_label(file_key),
                page_subtitle="Saved weekly report output file.",
            ),
            "snapshot": snapshot,
            "file_key": file_key,
            "file_label": report_file_label(file_key),
            "file_metadata": file_metadata,
            "file_content": file_content,
            "download_href": report_file_href(
                snapshot.get("snapshot_id", snapshot_id),
                file_key,
                download=True,
            ),
        },
    )


@app.get("/reports/{snapshot_id}/files/{file_key}/download")
async def download_report_file(snapshot_id: str, file_key: str):
    _, _, file_path = get_report_file_or_404(snapshot_id, file_key)

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="text/markdown",
    )


@app.get("/reports/{snapshot_id}/re-export/download")
async def download_report_re_export(snapshot_id: str):
    snapshot = get_report_snapshot_or_404(snapshot_id)
    markdown = build_report_re_export_markdown(
        snapshot,
        content_reader=read_report_file_content_for_re_export,
    )

    return Response(
        content=markdown,
        media_type="text/markdown",
        headers={
            "Content-Disposition": (
                "attachment; "
                f'filename="{report_export_filename(snapshot_id)}"'
            ),
        },
    )


@app.get("/newsletter", response_class=HTMLResponse)
async def newsletter(
    request: Request,
):
    return templates.TemplateResponse(
        request,
        "newsletter_list.html",
        {
            **base_template_context(
                request,
                title="Weekly Brief",
                active_nav="newsletter",
                page_title="Weekly Brief",
                page_subtitle="Browse available weekly market intelligence briefs.",
            ),
            "briefs": [current_weekly_brief_item()],
        },
    )


@app.get("/newsletter/current", response_class=HTMLResponse)
async def current_newsletter(
    request: Request,
    topic: Optional[str] = None,
):
    selected_topic = normalize_newsletter_topic(topic)
    articles = newsletter_articles(topic=selected_topic)
    markdown_preview = newsletter_markdown(articles, topic=selected_topic)

    return templates.TemplateResponse(
        request,
        "newsletter.html",
        {
            **base_template_context(
                request,
                title="Weekly Brief",
                active_nav="newsletter",
                page_title="Weekly Brief",
                page_subtitle="A current view of high-signal market intelligence articles.",
            ),
            "topic_options": NEWSLETTER_TOPIC_OPTIONS,
            "topic": selected_topic,
            "articles": articles,
            "brief_date_range": current_week_label(),
            "markdown_preview": markdown_preview,
            "output_path": None,
            "message": None,
        },
    )


@app.post("/newsletter/export", response_class=HTMLResponse)
async def export_newsletter(
    request: Request,
    topic: str = Form(default=""),
):
    selected_topic = normalize_newsletter_topic(topic)
    articles = newsletter_articles(topic=selected_topic)
    markdown_preview = newsletter_markdown(articles, topic=selected_topic)
    output_path = newsletter_output_path(selected_topic)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_preview, encoding="utf-8")

    return templates.TemplateResponse(
        request,
        "newsletter.html",
        {
            **base_template_context(
                request,
                title="Weekly Brief",
                active_nav="newsletter",
                page_title="Weekly Brief",
                page_subtitle="A current view of high-signal market intelligence articles.",
            ),
            "topic_options": NEWSLETTER_TOPIC_OPTIONS,
            "topic": selected_topic,
            "articles": articles,
            "brief_date_range": current_week_label(),
            "markdown_preview": markdown_preview,
            "output_path": output_path,
            "message": "Weekly brief exported.",
        },
    )


@app.get("/review", response_class=HTMLResponse)
async def review_queue(
    request: Request,
    topic: Optional[str] = None,
    message: Optional[str] = None,
    error: Optional[str] = None,
):
    selected_topic = clean_filter(topic)

    return templates.TemplateResponse(
        request,
        "review_queue.html",
        {
            **base_template_context(
                request,
                title="Review Queue",
                page_title="Review Queue",
                page_subtitle="Manual review tools remain available at /review.",
            ),
            "articles": review_queue_articles(topic=selected_topic),
            "topic": selected_topic,
            "message": clean_filter(message),
            "error": clean_filter(error),
        },
    )


@app.post("/review/action", response_class=HTMLResponse)
async def review_action(
    article_id: str = Form(default=""),
    action: str = Form(default=""),
    topic: str = Form(default=""),
):
    selected_topic = clean_filter(topic)
    cleaned_article_id = clean_filter(article_id)
    cleaned_action = clean_filter(action)

    if cleaned_action not in {*REVIEW_ACTION_STATUS_UPDATES, "toggle_eligible"}:
        return RedirectResponse(
            url=review_queue_url(
                topic=selected_topic,
                error="Invalid review action.",
            ),
            status_code=303,
        )

    if cleaned_article_id is None:
        return RedirectResponse(
            url=review_queue_url(
                topic=selected_topic,
                error="Article not found.",
            ),
            status_code=303,
        )

    repository = get_knowledge_repository()
    article = repository.get_article(cleaned_article_id)
    if article is None:
        return RedirectResponse(
            url=review_queue_url(
                topic=selected_topic,
                error="Article not found.",
            ),
            status_code=303,
        )

    if cleaned_action == "toggle_eligible":
        updated_article = repository.update_article_review(
            cleaned_article_id,
            newsletter_eligible=not article.get("newsletter_eligible", False),
        )
    else:
        updated_article = repository.update_article_review(
            cleaned_article_id,
            review_status=REVIEW_ACTION_STATUS_UPDATES[cleaned_action],
        )

    if updated_article is None:
        return RedirectResponse(
            url=review_queue_url(
                topic=selected_topic,
                error="Article not found.",
            ),
            status_code=303,
        )

    return RedirectResponse(
        url=review_queue_url(
            topic=selected_topic,
            message="Review queue updated.",
        ),
        status_code=303,
    )


@app.get("/intake", response_class=HTMLResponse)
async def intake(request: Request):
    return templates.TemplateResponse(
        request,
        "intake.html",
        intake_context(request),
    )


@app.post("/intake", response_class=HTMLResponse)
async def create_manual_article(
    request: Request,
    url: str = Form(default=""),
    topic: str = Form(default=""),
    note: str = Form(default=""),
):
    form = {
        "url": url,
        "topic": topic,
        "note": note,
    }
    normalized_url, url_error = normalize_manual_article_url(url)
    cleaned_topic = clean_filter(topic)

    if url_error is not None:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                error=url_error,
            ),
            status_code=400,
        )

    if cleaned_topic is None:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                error="Choose a topic.",
            ),
            status_code=400,
        )

    if cleaned_topic not in INTAKE_TOPIC_OPTIONS:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                error="Choose a valid topic.",
            ),
            status_code=400,
        )

    repository = get_knowledge_repository()
    duplicate_article = repository.find_by_normalized_url(normalized_url)
    if duplicate_article is not None:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                duplicate_article=duplicate_article,
            ),
            status_code=200,
        )

    result = repository.create_manual_article(
        clean_filter(url),
        cleaned_topic,
        note.strip(),
        normalized_url=normalized_url,
    )
    article = result["article"]

    if result["duplicate"]:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                duplicate_article=article,
            ),
            status_code=200,
        )

    return RedirectResponse(
        url=f"{article_detail_href(article)}?created=1",
        status_code=303,
    )


@app.get("/articles/{article_id:path}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: str,
    saved: Optional[str] = None,
    created: Optional[str] = None,
    summary_requested: Optional[str] = None,
):
    repository = get_knowledge_repository()
    article = repository.get_article(article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    duplicate_article = None
    duplicate_detail_href = None
    duplicate_article_id = article.get("duplicate_of_article_id")
    if duplicate_article_id:
        duplicate_article = repository.get_article(duplicate_article_id)
        if duplicate_article is not None:
            duplicate_detail_href = article_detail_href(duplicate_article)

    return templates.TemplateResponse(
        request,
        "article_detail.html",
        {
            **base_template_context(
                request,
                title=article.get("title") or "Article Detail",
                active_nav="home",
                page_title=article.get("title") or "Article Detail",
            ),
            "article": article,
            "detail_href": article_detail_href(article),
            "summary_status_display": display_summary_status(article),
            "summary_status_bucket": article_summary_status_bucket(article),
            "summary_status_explanation": summary_status_explanation(article),
            "can_generate_summary": can_generate_summary(article),
            "can_retry_summary": is_retryable_failure(article),
            "duplicate_article": duplicate_article,
            "duplicate_detail_href": duplicate_detail_href,
            "recommendation_options": RECOMMENDATION_OPTIONS,
            "saved": saved == "1",
            "created": created == "1",
            "summary_requested": summary_requested == "1",
        },
    )


@app.post("/articles/{article_id:path}/generate-summary", response_class=HTMLResponse)
async def generate_article_summary(article_id: str):
    repository = get_knowledge_repository()
    service = get_article_processing_service(repository)
    result = service.process_article(article_id)

    if result.not_found:
        raise HTTPException(status_code=404, detail="Article not found")

    article = result.article or repository.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(
        url=f"{article_detail_href(article)}?summary_requested=1",
        status_code=303,
    )


@app.post("/articles/{article_id:path}/summary", response_class=HTMLResponse)
async def request_article_summary(article_id: str):
    return await generate_article_summary(article_id)


@app.post(
    "/articles/{article_id:path}/retry-generate-summary",
    response_class=HTMLResponse,
)
async def retry_article_summary(article_id: str):
    repository = get_knowledge_repository()
    article = repository.get_article(article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    if not is_retryable_failure(article):
        return RedirectResponse(
            url=article_detail_href(article),
            status_code=303,
        )

    service = get_article_processing_service(repository)
    result = service.process_article(article_id)

    if result.not_found:
        raise HTTPException(status_code=404, detail="Article not found")

    article = result.article or repository.get_article(article_id)
    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(
        url=f"{article_detail_href(article)}?summary_requested=1",
        status_code=303,
    )


@app.post("/articles/{article_id:path}/delete", response_class=HTMLResponse)
async def delete_article(article_id: str):
    repository = get_knowledge_repository()
    article = repository.get_article(article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    deleted_article = repository.delete_article(article_id)
    if deleted_article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(url="/", status_code=303)


@app.post("/articles/{article_id:path}", response_class=HTMLResponse)
async def update_article_recommendation(
    article_id: str,
    recommendation: str = Form(...),
):
    if recommendation not in RECOMMENDATION_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid recommendation")

    repository = get_knowledge_repository()
    article = repository.update_article_recommendation(
        article_id,
        recommendation=recommendation,
    )

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(
        url=f"{article_detail_href(article)}?saved=1",
        status_code=303,
    )
