import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote, urlencode

from config import RSS_SOURCES_BY_TOPIC, SOURCES
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
NEWSLETTER_OUTPUT_DIR = REPO_ROOT / "outputs" / "newsletter"
KEYWORDS_CONFIG_PATH = REPO_ROOT / "config" / "keywords.json"

app = FastAPI(title="Market Intelligence Agent 2.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

NAVIGATION_ITEMS = [
    {"key": "home", "label": "Dashboard", "href": "/"},
    {"key": "newsletter", "label": "Weekly Brief", "href": "/newsletter"},
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
    {"value": "failed", "label": "Failed"},
    {"value": "to_extract", "label": "To Extract"},
    {"value": "all", "label": "All"},
]
SUMMARY_STATUS_FILTERS = {tab["value"] for tab in SUMMARY_STATUS_TABS}
DEFAULT_SUMMARY_STATUS_FILTER = "ready"
RECOMMENDATION_OPTIONS = ["Core", "Useful", "Exclude"]


def get_knowledge_repository():
    return JsonKnowledgeRepository()


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

    return "To Extract"


def summary_status_explanation(article):
    bucket = article_summary_status_bucket(article)
    if bucket == "ready":
        return "Summary is available for this article."
    if bucket == "failed":
        return "Summary generation failed. You can try generating it again."

    return "This article has not been summarized yet."


def can_generate_summary(article):
    return article_summary_status_bucket(article) != "ready"


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
    recommendation = str(article.get("recommendation") or "").casefold()
    if recommendation == "core":
        return 3
    if recommendation == "useful":
        return 2
    return 0


def weekly_brief_candidate_articles(topic=None):
    repository = get_knowledge_repository()
    articles = repository.list_articles(topic=topic)

    recommended_articles = [
        article
        for article in articles
        if recommendation_rank(article) > 0
    ]
    candidates = recommended_articles or articles

    sorted_candidates = sorted(
        candidates,
        key=lambda article: (
            recommendation_rank(article),
            article_score(article),
            str(article.get("updated_at") or article.get("created_at") or ""),
        ),
        reverse=True,
    )
    return with_detail_hrefs(sorted_candidates)


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
    recommendation: Optional[str] = None,
    page: Optional[str] = None,
):
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
            summary_status=summary_status,
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
    cleaned_url = clean_filter(url)
    cleaned_topic = clean_filter(topic)

    if cleaned_url is None:
        return templates.TemplateResponse(
            request,
            "intake.html",
            intake_context(
                request,
                form=form,
                error="URL is required.",
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
    result = repository.create_manual_article(
        cleaned_url,
        cleaned_topic,
        note.strip(),
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
            "recommendation_options": RECOMMENDATION_OPTIONS,
            "saved": saved == "1",
            "created": created == "1",
            "summary_requested": summary_requested == "1",
        },
    )


@app.post("/articles/{article_id:path}/summary", response_class=HTMLResponse)
async def request_article_summary(article_id: str):
    repository = get_knowledge_repository()
    article = repository.get_article(article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(
        url=f"{article_detail_href(article)}?summary_requested=1",
        status_code=303,
    )


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
