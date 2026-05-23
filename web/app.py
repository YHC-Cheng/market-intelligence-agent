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
    "/intake": "Manual Intake",
    "/review": "Review Queue",
    "/newsletter": "Newsletter Draft",
}

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


@app.get("/articles/{article_id:path}", response_class=HTMLResponse)
async def article_detail(
    request: Request,
    article_id: str,
    saved: Optional[str] = None,
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
