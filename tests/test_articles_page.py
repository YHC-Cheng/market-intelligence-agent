import json
from urllib.parse import quote

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sidebar_markup(response_text):
    start = response_text.index('<nav class="sidebar-nav">')
    end = response_text.index("</nav>", start)
    return response_text[start:end]


def detail_path(article_id):
    return f"/articles/{quote(article_id, safe='')}"


def article_client(monkeypatch, knowledge_path):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    return TestClient(app_module.app)


def test_articles_page_handles_empty_repository(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/")

    assert response.status_code == 200
    assert "Home" in response.text
    assert "Weekly Brief" in response.text
    assert "high-signal market intelligence summary" in response.text
    assert 'href="/newsletter">Open brief</a>' in response.text
    assert "No articles found" in response.text


def test_articles_route_redirects_to_home(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/articles", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/"


def test_articles_route_redirect_preserves_query_string(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get(
        "/articles?topic=FinOps&keyword=agent",
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"] == "/?topic=FinOps&keyword=agent"


def test_main_navigation_uses_phase_2_sidebar_items(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/")
    sidebar = sidebar_markup(response.text)

    assert response.status_code == 200
    assert 'href="/"' in sidebar
    assert "Home" in sidebar
    assert 'href="/reference"' in sidebar
    assert "Reference" in sidebar
    assert 'href="/intake"' not in sidebar
    assert "Add Article" not in sidebar
    assert 'href="/newsletter"' not in sidebar
    assert "Weekly Brief" not in sidebar
    assert 'href="/review"' not in sidebar
    assert "Review Queue" not in sidebar


def test_reference_page_displays_keywords_and_source_links(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/reference")

    assert response.status_code == 200
    assert "Keywords" in response.text
    assert "Source Links" in response.text
    assert "AI" in response.text
    assert "OpenAI News RSS" in response.text
    assert "https://openai.com/news/rss.xml" in response.text


def test_articles_page_displays_repository_articles(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/cloud-costs": {
                "url": "https://example.com/cloud-costs",
                "title": "Cloud cost control",
                "topic": "FinOps",
                "source": "Example Blog",
                "score": 88.0,
                "review_status": "approved",
                "newsletter_eligible": True,
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Cloud cost control" in response.text
    assert "FinOps" in response.text
    assert "Example Blog" in response.text
    assert "88.0" in response.text
    assert 'href="/articles/https%3A%2F%2Fexample.com%2Fcloud-costs"' in response.text
    assert '<th scope="col">Action</th>' not in response.text
    assert "approved for downstream use" not in response.text
    assert "review readiness" not in response.text
    assert "newsletter eligible" not in response.text.casefold()


def test_articles_page_filters_by_topic(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/finops": {
                "url": "https://example.com/finops",
                "title": "FinOps cloud report",
                "topic": "FinOps",
                "source": "Example",
            },
            "https://example.com/security": {
                "url": "https://example.com/security",
                "title": "Security update",
                "topic": "Security",
                "source": "Example",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?topic=FinOps")

    assert response.status_code == 200
    assert "FinOps cloud report" in response.text
    assert "Security update" not in response.text


def test_articles_page_filters_by_keyword(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/cloud": {
                "url": "https://example.com/cloud",
                "title": "Cloud planning guide",
                "topic": "FinOps",
                "source": "Example",
            },
            "https://example.com/security": {
                "url": "https://example.com/security",
                "title": "Security update",
                "topic": "Security",
                "source": "Example",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?keyword=cloud")

    assert response.status_code == 200
    assert "Cloud planning guide" in response.text
    assert "Security update" not in response.text


def test_article_detail_page_displays_article(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Detailed article",
                "topic": "FinOps",
                "source": "Example Blog",
                "ranking_score": 77,
                "summary": "Useful summary.",
                "use_case": "Cloud cost reporting",
                "problem_solved": "Manual review is slow.",
                "recommendation": "Core",
                "review_status": "unreviewed",
                "newsletter_eligible": False,
                "review_note": "Initial note",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/articles/article-1")

    assert response.status_code == 200
    assert "Detailed article" in response.text
    assert "FinOps" in response.text
    assert "Example Blog" in response.text
    assert "77" in response.text
    assert "Useful summary." in response.text
    assert "Cloud cost reporting" in response.text
    assert "Manual review is slow." in response.text
    assert "Core" in response.text
    assert "Legacy review controls" not in response.text
    assert "Weekly brief eligible" not in response.text
    assert "Review Status" not in response.text
    assert "unreviewed" not in response.text
    assert "Initial note" not in response.text
    assert 'href="https://example.com/article-1"' in response.text


def test_article_detail_page_supports_url_article_ids(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/url-id": {
                "url": "https://example.com/url-id",
                "title": "URL id article",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get(detail_path("https://example.com/url-id"))

    assert response.status_code == 200
    assert "URL id article" in response.text


def test_article_detail_page_returns_404_for_missing_article(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/articles/missing")

    assert response.status_code == 404
    assert "Article not found" in response.text


def test_article_review_form_updates_review_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Review me",
                "custom_field": {"keep": True},
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.post(
        "/articles/article-1",
        data={"review_status": "approved", "review_note": ""},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Internal metadata saved." in response.text
    assert persisted["review_status"] == "approved"
    assert persisted["custom_field"] == {"keep": True}


def test_article_review_form_updates_newsletter_eligible(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Newsletter candidate",
                "newsletter_eligible": False,
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.post(
        "/articles/article-1",
        data={"review_status": "unreviewed", "newsletter_eligible": "true"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Internal metadata saved." in response.text
    assert persisted["newsletter_eligible"] is True


def test_article_review_form_updates_review_note(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Needs a note",
                "review_note": "",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.post(
        "/articles/article-1",
        data={
            "review_status": "needs_fix",
            "review_note": "Needs a clearer source summary.",
        },
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Internal metadata saved." in response.text
    assert persisted["review_note"] == "Needs a clearer source summary."
