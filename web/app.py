from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


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
    "/articles": "Knowledge Explorer",
    "/intake": "Manual Intake",
    "/review": "Review Queue",
    "/newsletter": "Newsletter Draft",
}


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
