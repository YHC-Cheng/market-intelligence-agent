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


def summary_tabs_markup(response_text):
    start = response_text.index('<nav class="status-tabs"')
    end = response_text.index("</nav>", start)
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


def detail_section_markup(response_text, heading):
    heading_index = response_text.index(heading)
    start = response_text.rfind("<section", 0, heading_index)
    end = response_text.index("</section>", heading_index)
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
            "summary_status": "ready",
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
    assert 'href="/newsletter/current">Open brief</a>' in response.text
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
    assert "Dashboard" in sidebar
    assert 'href="/newsletter"' in sidebar
    assert "Weekly Brief" in sidebar
    assert 'href="/reference"' in sidebar
    assert "Reference" in sidebar
    assert 'href="/intake"' not in sidebar
    assert "Add Article" not in sidebar
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
                "summary_status": "ready",
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
                "summary_status": "ready",
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
    assert "All Recommendations" in filters
    assert 'name="source"' not in filters
    assert 'name="type"' not in filters
    assert "All Summary Statuses" not in filters


def test_articles_page_renders_summary_status_tabs(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Ready article",
                "summary_status": "ready",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")
    stylesheet = client.get("/static/style.css")
    tabs = summary_tabs_markup(response.text)
    filter_index = response.text.index('<form class="filters-row article-filters"')
    tabs_index = response.text.index('<nav class="status-tabs"')
    table_index = response.text.index('<table class="data-table article-table">')

    assert response.status_code == 200
    assert 'id="articles-section"' in response.text
    assert filter_index < tabs_index < table_index
    assert 'href="/?summary_status=ready"' in tabs
    assert "Ready" in tabs
    assert 'href="/?summary_status=failed"' in tabs
    assert "Failed" in tabs
    assert 'href="/?summary_status=to_extract"' in tabs
    assert "To Extract" in tabs
    assert "To-do" not in tabs
    assert "Needs Summary" not in tabs
    assert 'href="/?summary_status=all"' in tabs
    assert "All" in tabs
    assert 'class="status-tab is-active"' in tabs
    assert 'aria-current="page"' in tabs
    assert ".status-tabs {\n  display: flex;" in stylesheet.text
    assert "grid-template-columns: repeat(4, 1fr);" not in stylesheet.text
    assert "dashboardArticlesScrollY" in response.text
    assert "sessionStorage" in response.text


def test_summary_status_tabs_preserve_existing_filters(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Cloud cost control",
                "topic": "FinOps",
                "summary": "Cost summary.",
                "summary_status": "ready",
                "recommendation": "Core",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get(
        "/?keyword=cloud&topic=FinOps&recommendation=Core",
    )
    tabs = summary_tabs_markup(response.text)

    assert response.status_code == 200
    assert (
        'href="/?summary_status=failed&amp;keyword=cloud'
        '&amp;topic=FinOps&amp;recommendation=Core"'
    ) in tabs


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
                "summary_status": "ready",
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

    response = client.get("/?summary_status=all&topic=FinOps")

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
                "summary_status": "ready",
            },
            "https://example.com/pending": {
                "url": "https://example.com/pending",
                "title": "Pending intelligence",
                "analysis_status": "pending",
            },
            "https://example.com/to-extract": {
                "url": "https://example.com/to-extract",
                "title": "To extract intelligence",
                "summary_status": "to_extract",
            },
            "https://example.com/failed": {
                "url": "https://example.com/failed",
                "title": "Failed intelligence",
                "summary_status": "failed",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "Ready intelligence" in response.text
    assert "Pending intelligence" not in response.text
    assert "To extract intelligence" not in response.text
    assert "Failed intelligence" not in response.text

    response = client.get("/?summary_status=failed")

    assert response.status_code == 200
    assert "Failed intelligence" in response.text
    assert "Ready intelligence" not in response.text
    assert "Pending intelligence" not in response.text
    assert "To extract intelligence" not in response.text

    response = client.get("/?summary_status=to_extract")

    assert response.status_code == 200
    assert "Pending intelligence" in response.text
    assert "To extract intelligence" in response.text
    assert "Ready intelligence" not in response.text
    assert "Failed intelligence" not in response.text

    response = client.get("/?summary_status=needs_summary")

    assert response.status_code == 200
    assert "Pending intelligence" in response.text
    assert "To extract intelligence" in response.text
    assert "Ready intelligence" not in response.text
    assert "Failed intelligence" not in response.text

    response = client.get("/?summary_status=all")

    assert response.status_code == 200
    assert "Ready intelligence" in response.text
    assert "Pending intelligence" in response.text
    assert "To extract intelligence" in response.text
    assert "Failed intelligence" in response.text


def test_articles_to_extract_tab_includes_legacy_unprocessed_statuses(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "missing": {
                "id": "missing",
                "title": "Missing status intelligence",
                "summary": "Existing text without a processing state.",
            },
            "empty": {
                "id": "empty",
                "title": "Empty status intelligence",
                "summary_status": "",
            },
            "not-started": {
                "id": "not-started",
                "title": "Not started intelligence",
                "analysis_status": "not_started",
            },
            "pending": {
                "id": "pending",
                "title": "Pending status intelligence",
                "analysis_status": "pending",
            },
            "needs-summary": {
                "id": "needs-summary",
                "title": "Needs summary intelligence",
                "summary_status": "needs_summary",
            },
            "to-extract": {
                "id": "to-extract",
                "title": "To Extract status intelligence",
                "summary_status": "to_extract",
            },
            "ready": {
                "id": "ready",
                "title": "Ready status intelligence",
                "summary_status": "ready",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?summary_status=to_extract")

    assert response.status_code == 200
    assert "Missing status intelligence" in response.text
    assert "Empty status intelligence" in response.text
    assert "Not started intelligence" in response.text
    assert "Pending status intelligence" in response.text
    assert "Needs summary intelligence" in response.text
    assert "To Extract status intelligence" in response.text
    assert "Ready status intelligence" not in response.text
    assert "To Extract" in response.text
    assert "To-do" not in response.text


def test_articles_invalid_summary_status_falls_back_safely(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "ready": {
                "id": "ready",
                "title": "Ready fallback intelligence",
                "summary_status": "ready",
            },
            "pending": {
                "id": "pending",
                "title": "Pending fallback intelligence",
                "summary_status": "to_extract",
            },
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/?summary_status=unknown")
    tabs = summary_tabs_markup(response.text)

    assert response.status_code == 200
    assert "Ready fallback intelligence" in response.text
    assert "Pending fallback intelligence" not in response.text
    assert 'class="status-tab is-active"' in tabs
    assert 'href="/?summary_status=ready"' in tabs
    assert 'aria-current="page"' in tabs


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

    response = client.get("/?summary_status=all&recommendation=Core")

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

    response = client.get("/?summary_status=all&keyword=cloud")

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

    response = client.get("/?summary_status=all")

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
    assert 'href="/?summary_status=ready&amp;page=2">Next</a>' in response.text


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


def test_article_detail_shows_summary_processing_for_ready_article(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Ready article",
                "summary": "Useful summary.",
                "summary_status": "ready",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/articles/article-1")
    section = detail_section_markup(response.text, "Summary Processing")

    assert response.status_code == 200
    assert "Summary Processing" in section
    assert "Summary Status" in section
    assert "Ready" in section
    assert "Summary is available for this article." in section
    assert "Generate Summary" not in section


def test_article_detail_shows_generate_summary_for_unready_states(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "missing": {
                "id": "missing",
                "title": "Missing status article",
            },
            "not-started": {
                "id": "not-started",
                "title": "Not started article",
                "analysis_status": "not_started",
            },
            "pending": {
                "id": "pending",
                "title": "Pending article",
                "analysis_status": "pending",
            },
            "failed": {
                "id": "failed",
                "title": "Failed article",
                "summary_status": "failed",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    for article_id in ["missing", "not-started", "pending", "failed"]:
        response = client.get(f"/articles/{article_id}")
        section = detail_section_markup(response.text, "Summary Processing")

        assert response.status_code == 200
        assert "Generate Summary" in section
        if article_id != "failed":
            assert "To Extract" in section

    failed_response = client.get("/articles/failed")
    failed_section = detail_section_markup(
        failed_response.text,
        "Summary Processing",
    )
    assert (
        "Summary generation failed. You can try generating it again."
        in failed_section
    )


def test_article_summary_placeholder_route_redirects_without_generation(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Needs summary",
                "summary_status": "to_extract",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.post(
        "/articles/article-1/summary",
        follow_redirects=False,
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 303
    assert response.headers["location"] == "/articles/article-1?summary_requested=1"
    assert persisted["summary_status"] == "to_extract"
    assert "summary" not in persisted

    response = client.post("/articles/article-1/summary")

    assert response.status_code == 200
    assert "Summary generation will be connected in a later phase." in response.text
    assert "Summary generated" not in response.text


def test_article_detail_shows_compact_recommendation_editor_in_header(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Recommendation article",
                "recommendation": "Useful",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.get("/articles/article-1")
    metadata = article_metadata_markup(response.text)

    assert response.status_code == 200
    assert "Recommendation Management" not in response.text
    assert 'class="metadata-recommendation-form"' in metadata
    assert 'class="recommendation-select-badge"' in metadata
    assert 'name="recommendation"' in metadata
    assert 'onchange="this.form.submit()"' in metadata
    assert 'value="Core"' in metadata
    assert 'value="Useful"' in metadata
    assert 'value="Exclude"' in metadata
    assert 'value="Useful" selected' in metadata
    assert ">Save</button>" not in metadata


def test_article_recommendation_form_updates_recommendation(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Recommendation candidate",
                "summary_status": "ready",
                "summary": "Useful summary.",
                "recommendation": "Useful",
                "custom_field": {"keep": True},
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    response = client.post(
        "/articles/article-1",
        data={"recommendation": "Core"},
        follow_redirects=False,
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 303
    assert response.headers["location"] == "/articles/article-1?saved=1"
    assert persisted["recommendation"] == "Core"
    assert persisted["custom_field"] == {"keep": True}

    response = client.post(
        "/articles/article-1",
        data={"recommendation": "Exclude"},
    )

    assert response.status_code == 200
    assert "Recommendation updated." in response.text


def test_dashboard_reflects_updated_recommendation(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article-1",
                "title": "Dashboard recommendation candidate",
                "summary_status": "ready",
                "recommendation": "Useful",
            }
        },
    )
    client = article_client(monkeypatch, knowledge_path)

    client.post("/articles/article-1", data={"recommendation": "Core"})
    response = client.get("/")
    table_body = articles_table_body_markup(response.text)

    assert response.status_code == 200
    assert "Dashboard recommendation candidate" in table_body
    assert "Core" in table_body
