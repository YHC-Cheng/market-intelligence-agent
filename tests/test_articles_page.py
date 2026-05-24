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


def articles_filter_markup(response_text):
    start = response_text.index('<form class="filters-row article-filters"')
    end = response_text.index("</form>", start)
    return response_text[start:end]


def articles_table_head_markup(response_text):
    start = response_text.index('<table class="data-table article-table">')
    head_start = response_text.index("<thead>", start)
    head_end = response_text.index("</thead>", head_start)
    return response_text[head_start:head_end]


def articles_table_body_markup(response_text):
    start = response_text.index('<table class="data-table article-table">')
    body_start = response_text.index("<tbody>", start)
    body_end = response_text.index("</tbody>", body_start)
    return response_text[body_start:body_end]


def articles_pagination_markup(response_text):
    start = response_text.index('<nav class="pagination"')
    end = response_text.index("</nav>", start)
    return response_text[start:end]


def article_metadata_markup(response_text):
    start = response_text.index('<div class="metadata-row"')
    end = response_text.index("</div>", start)
    return response_text[start:end]


def article_info_markup(response_text):
    start = response_text.index('<aside class="article-info-card"')
    end = response_text.index("</aside>", start)
    return response_text[start:end]


def detail_path(article_id):
    return f"/articles/{quote(article_id, safe='')}"


def article_client(monkeypatch, knowledge_path):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    return TestClient(app_module.app)


def numbered_articles(count, **overrides):
    return {
        f"article-{index:02d}": {
            "id": f"article-{index:02d}",
            "title": f"Article {index:02d}",
            "topic": "FinOps",
            "summary": f"cloud summary {index:02d}",
            "recommendation": "Core",
            "updated_at": f"2026-05-{index:02d}T14:22:31",
            **overrides,
        }
        for index in range(1, count + 1)
    }


def test_articles_page_handles_empty_repository(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/")

    assert response.status_code == 200
    assert "<h1>Dashboard</h1>" in response.text
    assert "Weekly Brief" in response.text
    assert "high-signal market intelligence summary" in response.text
    assert 'href="/newsletter">Open brief</a>' in response.text
    assert 'href="/intake"' in response.text
    assert "Add Article" in response.text
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
                "summary": "Cost summary.",
                "recommendation": "Core",
                "updated_at": "2026-05-17T14:22:31",
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
    assert "ready" in response.text
    assert "Core" in response.text
    assert "2026-05-17" in response.text
    assert "2026-05-17T14:22:31" not in response.text
    assert "Example Blog" not in response.text
    assert "88.0" not in response.text
    assert 'href="/articles/https%3A%2F%2Fexample.com%2Fcloud-costs"' in response.text
    assert "approved for downstream use" not in response.text
    assert "review readiness" not in response.text
    assert "newsletter eligible" not in response.text.casefold()


def test_articles_filters_use_phase_2_dashboard_fields(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Cloud cost control",
                "topic": "FinOps",
                "summary": "Cost summary.",
                "recommendation": "Core",
                "source": "Example Blog",
                "ingestion_type": "rss",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")
    filters = articles_filter_markup(response.text)

    assert response.status_code == 200
    assert "Keyword search" in filters
    assert 'name="keyword"' in filters
    assert 'name="topic"' in filters
    assert 'name="summary_status"' in filters
    assert 'name="recommendation"' in filters
    assert "All Summary Statuses" in filters
    assert "All Recommendations" in filters
    assert 'name="source"' not in filters
    assert 'name="type"' not in filters
    assert "All Sources" not in filters
    assert "All Types" not in filters


def test_keyword_search_input_does_not_render_search_icon(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/")
    filters = articles_filter_markup(response.text)
    stylesheet = client.get("/static/style.css")

    assert response.status_code == 200
    assert 'placeholder="Keyword search"' in filters
    assert "search-field" not in filters
    assert "search-control" not in filters
    assert "search-field::before" not in stylesheet.text
    assert "search-field::after" not in stylesheet.text


def test_articles_table_uses_phase_2_dashboard_columns(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Cloud cost control",
                "topic": "FinOps",
                "summary": "Cost summary.",
                "recommendation": "Core",
                "source": "Example Blog",
                "ingestion_type": "rss",
                "score": 88.0,
                "updated_at": "2026-05-17T14:22:31",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")
    table_head = articles_table_head_markup(response.text)

    assert response.status_code == 200
    assert '<th scope="col">Title</th>' in table_head
    assert '<th scope="col">Topic</th>' in table_head
    assert '<th scope="col">Summary Status</th>' in table_head
    assert '<th scope="col">Recommendation</th>' in table_head
    assert '<th scope="col">Updated</th>' in table_head
    assert '<th scope="col">Source</th>' not in table_head
    assert '<th scope="col">Type</th>' not in table_head
    assert '<th scope="col">Score</th>' not in table_head
    assert '<th scope="col">Action</th>' not in table_head
    assert '<th scope="col">View</th>' not in table_head


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


def test_articles_page_filters_by_summary_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/ready": {
                "url": "https://example.com/ready",
                "title": "Ready intelligence",
                "summary": "A complete summary.",
            },
            "https://example.com/pending": {
                "url": "https://example.com/pending",
                "title": "Pending intelligence",
                "analysis_status": "pending",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?summary_status=ready")

    assert response.status_code == 200
    assert "Ready intelligence" in response.text
    assert "Pending intelligence" not in response.text


def test_articles_page_filters_by_recommendation(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/core": {
                "url": "https://example.com/core",
                "title": "Core intelligence",
                "recommendation": "Core",
            },
            "https://example.com/useful": {
                "url": "https://example.com/useful",
                "title": "Useful intelligence",
                "recommendation": "Useful",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?recommendation=Core")

    assert response.status_code == 200
    assert "Core intelligence" in response.text
    assert "Useful intelligence" not in response.text


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


def test_articles_page_renders_missing_values_as_dash(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "updated_at": "not-a-date",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "—" in response.text
    assert "not-a-date" not in response.text


def test_articles_page_shows_at_most_15_articles_per_page(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")
    table_body = articles_table_body_markup(response.text)

    assert response.status_code == 200
    assert table_body.count('class="title-link"') == 15
    assert "Article 01" in table_body
    assert "Article 15" in table_body
    assert "Article 16" not in table_body


def test_articles_page_renders_pagination_for_more_than_15_articles(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Showing 1–15 of 16 articles" in response.text
    assert "Page 1 of 2" in response.text
    assert '<span class="button button-secondary button-sm is-disabled" aria-disabled="true">Previous</span>' in response.text
    assert 'href="/?page=2">Next</a>' in response.text


def test_articles_page_query_parameter_changes_visible_article_set(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?page=2")
    table_body = articles_table_body_markup(response.text)

    assert response.status_code == 200
    assert "Article 16" in table_body
    assert "Article 01" not in table_body
    assert "Showing 16–16 of 16 articles" in response.text
    assert "Page 2 of 2" in response.text


def test_articles_pagination_links_preserve_filter_query_parameters(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get(
        "/?keyword=cloud&topic=FinOps&summary_status=ready&recommendation=Core",
    )
    pagination = articles_pagination_markup(response.text)

    assert response.status_code == 200
    assert (
        'href="/?keyword=cloud&amp;topic=FinOps&amp;summary_status=ready'
        '&amp;recommendation=Core&amp;page=2">Next</a>'
    ) in pagination


def test_articles_invalid_page_values_fall_back_safely(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?page=not-a-number")
    table_body = articles_table_body_markup(response.text)

    assert response.status_code == 200
    assert "Article 01" in table_body
    assert "Article 16" not in table_body
    assert "Page 1 of 2" in response.text


def test_articles_page_beyond_last_page_falls_back_to_last_page(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(knowledge_path, numbered_articles(16))
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?page=99")
    table_body = articles_table_body_markup(response.text)

    assert response.status_code == 200
    assert "Article 16" in table_body
    assert "Article 01" not in table_body
    assert "Page 2 of 2" in response.text


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


def test_article_detail_displays_manual_ingestion_once_with_clear_label(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/pricing",
                "title": "Pricing article",
                "topic": "ProductObservation",
                "source": "manual",
                "ingestion_type": "manual",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/articles/article-1")
    metadata = article_metadata_markup(response.text).casefold()
    article_info = article_info_markup(response.text)

    assert response.status_code == 200
    assert metadata.count("manual") == 0
    assert "<dt>Ingestion Type</dt>" in article_info
    assert "<dd>Manual</dd>" in article_info
    assert "<dd>manual</dd>" not in article_info


def test_article_detail_hides_review_workflow_language(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/pricing",
                "title": "Pricing article",
                "topic": "ProductObservation",
                "source": "manual",
                "ingestion_type": "manual",
                "review_status": "approved",
                "newsletter_eligible": True,
                "review_note": "Internal note",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/articles/article-1")
    page_text = response.text.casefold()

    assert response.status_code == 200
    assert "reviewed" not in page_text
    assert "approved" not in page_text
    assert "newsletter eligible" not in page_text
    assert "review readiness" not in page_text
    assert "weekly brief eligible" not in page_text
    assert "internal note" not in page_text


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
