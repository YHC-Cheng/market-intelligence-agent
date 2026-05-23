from pathlib import Path
from typing import Optional
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Market Intelligence Agent 2.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

NAVIGATION_ITEMS = [
    {"label": "Knowledge Explorer", "href": "/articles"},
    {"label": "Manual Intake", "href": "/intake"},
    {"label": "Review Queue", "href": "/review"},
    {"label": "Newsletter Draft", "href": "/newsletter"},
]

PLACEHOLDER_PAGES = {
    "/review": "Review Queue",
    "/newsletter": "Newsletter Draft",
}

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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "title": "Market Intelligence Agent 2.0",
            "navigation_items": NAVIGATION_ITEMS,
            "page_name": None,
        },
    )


def get_knowledge_repository():
    return JsonKnowledgeRepository()


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


def intake_context(
    request: Request,
    form=None,
    error=None,
    duplicate_article=None,
):
    duplicate_detail_href = None
    if duplicate_article is not None:
        duplicate_detail_href = article_detail_href(duplicate_article)

    return {
        "request": request,
        "title": "Manual Intake",
        "navigation_items": NAVIGATION_ITEMS,
        "topic_options": INTAKE_TOPIC_OPTIONS,
        "form": form or {"url": "", "topic": "", "note": ""},
        "error": error,
        "duplicate_article": duplicate_article,
        "duplicate_detail_href": duplicate_detail_href,
    }


@app.get("/articles", response_class=HTMLResponse)
async def articles(
    request: Request,
    topic: Optional[str] = None,
    keyword: Optional[str] = None,
    review_status: Optional[str] = None,
    newsletter_eligible: Optional[str] = Query(default=None),
):
    filters = {
        "topic": clean_filter(topic),
        "keyword": clean_filter(keyword),
        "review_status": clean_filter(review_status),
        "newsletter_eligible": clean_filter(newsletter_eligible),
    }
    repository = get_knowledge_repository()
    article_list = repository.list_articles(
        topic=filters["topic"],
        keyword=filters["keyword"],
        review_status=filters["review_status"],
        newsletter_eligible=parse_bool_filter(filters["newsletter_eligible"]),
    )

    return templates.TemplateResponse(
        request,
        "articles.html",
        {
            "title": "Knowledge Explorer",
            "navigation_items": NAVIGATION_ITEMS,
            "articles": with_detail_hrefs(article_list),
            "filters": filters,
        },
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
):
    repository = get_knowledge_repository()
    article = repository.get_article(article_id)

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return templates.TemplateResponse(
        request,
        "article_detail.html",
        {
            "title": article.get("title") or "Article Detail",
            "navigation_items": NAVIGATION_ITEMS,
            "article": article,
            "detail_href": article_detail_href(article),
            "review_status_options": REVIEW_STATUS_OPTIONS,
            "saved": saved == "1",
            "created": created == "1",
        },
    )


@app.post("/articles/{article_id:path}", response_class=HTMLResponse)
async def update_article_review(
    article_id: str,
    review_status: str = Form(...),
    newsletter_eligible: bool = Form(False),
    review_note: Optional[str] = Form(default=""),
):
    if review_status not in REVIEW_STATUS_OPTIONS:
        raise HTTPException(status_code=400, detail="Invalid review status")

    repository = get_knowledge_repository()
    article = repository.update_article_review(
        article_id,
        review_status=review_status,
        newsletter_eligible=newsletter_eligible,
        review_note=review_note or "",
    )

    if article is None:
        raise HTTPException(status_code=404, detail="Article not found")

    return RedirectResponse(
        url=f"{article_detail_href(article)}?saved=1",
        status_code=303,
    )


def create_placeholder_route(page_name: str):
    async def placeholder(request: Request):
        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "title": page_name,
                "navigation_items": NAVIGATION_ITEMS,
                "page_name": page_name,
            },
        )

    return placeholder


for path, page_name in PLACEHOLDER_PAGES.items():
    app.add_api_route(
        path,
        create_placeholder_route(page_name),
        methods=["GET"],
        response_class=HTMLResponse,
    )
