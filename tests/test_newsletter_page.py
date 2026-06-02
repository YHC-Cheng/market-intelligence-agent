import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def section_markup(response_text, section_start):
    start = response_text.index(section_start)
    end = response_text.index("</section>", start)
    return response_text[start:end]


def brief_index_table_markup(response_text):
    start = response_text.index('<table class="data-table brief-index-table">')
    end = response_text.index("</table>", start)
    return response_text[start:end]


def brief_overview_markup(response_text):
    return section_markup(
        response_text,
        '<section class="card weekly-brief-card" aria-labelledby="brief-overview-title">',
    )


def markdown_preview_markup(response_text):
    return section_markup(
        response_text,
        '<section class="card markdown-preview newsletter-preview">',
    )


def newsletter_client(monkeypatch, knowledge_path, output_dir):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    monkeypatch.setattr(app_module, "NEWSLETTER_OUTPUT_DIR", output_dir)
    return TestClient(app_module.app)


def assert_no_retired_weekly_brief_language(response_text):
    page_text = response_text.casefold()

    assert "Newsletter Draft" not in response_text
    assert "reviewed" not in page_text
    assert "approved" not in page_text
    assert "newsletter eligible" not in page_text
    assert "review readiness" not in page_text
    assert "No brief candidates" not in response_text
    assert "No eligible articles" not in response_text
    assert "Phase 2.2 fallback ranking" not in response_text


def test_newsletter_page_displays_weekly_brief_list(tmp_path, monkeypatch):
    client = newsletter_client(
        monkeypatch,
        tmp_path / "articles_knowledge.json",
        tmp_path / "newsletter",
    )

    response = client.get("/newsletter")
    table = brief_index_table_markup(response.text)

    assert response.status_code == 200
    assert "Market Intelligence agent" in response.text
    assert "Weekly Brief" in response.text
    assert "<h1>Weekly Brief</h1>" in response.text
    assert "Browse available weekly market intelligence briefs." in response.text
    assert '<table class="data-table brief-index-table">' in response.text
    assert "<th scope=\"col\">Brief</th>" in table
    assert "<th scope=\"col\">Period</th>" in table
    assert "<th scope=\"col\">Articles</th>" in table
    assert "<th scope=\"col\">Status</th>" in table
    assert "<th scope=\"col\">Updated</th>" in table
    assert "<th scope=\"col\">Action</th>" not in table
    assert '<a href="/newsletter/current" class="title-link">Current Weekly Brief</a>' in table
    assert "Open brief" not in table
    assert "Current</span>" in table
    assert_no_retired_weekly_brief_language(response.text)


def test_current_newsletter_page_displays_weekly_brief_detail(
    tmp_path,
    monkeypatch,
):
    client = newsletter_client(
        monkeypatch,
        tmp_path / "articles_knowledge.json",
        tmp_path / "newsletter",
    )

    response = client.get("/newsletter/current")
    overview = brief_overview_markup(response.text)
    preview = markdown_preview_markup(response.text)

    assert response.status_code == 200
    assert "Market Intelligence agent" in response.text
    assert "Weekly Brief" in response.text
    assert "<h1>Weekly Brief</h1>" in response.text
    assert "A current view of high-signal market intelligence articles." in response.text
    assert "Brief overview" in overview
    assert "High-signal articles" in response.text
    assert "Export markdown" not in overview
    assert "Markdown preview" in preview
    assert "Export markdown" in preview
    assert_no_retired_weekly_brief_language(response.text)


def test_newsletter_page_shows_high_signal_article_candidates(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "core": {
                "id": "core",
                "url": "https://example.com/core",
                "title": "Core market signal",
                "topic": "AI",
                "source": "Example",
                "score": 91,
                "summary_status": "ready",
                "summary": "A useful article.",
                "use_case": "Planning",
                "problem_solved": "Prioritization",
                "recommendation": "Core",
            },
            "useful": {
                "id": "useful",
                "title": "Useful FinOps signal",
                "topic": "FinOps",
                "source": "Example",
                "score": 74,
                "summary_status": "ready",
                "summary": "A useful FinOps article.",
                "recommendation": "Useful",
            },
            "low": {
                "id": "low",
                "title": "Low priority item",
                "score": 99,
                "summary_status": "ready",
                "summary": "A low priority article.",
                "recommendation": "Low",
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current")

    assert response.status_code == 200
    assert "Core market signal" in response.text
    assert "Useful FinOps signal" in response.text
    assert "A useful article." in response.text
    assert "Planning" in response.text
    assert "Prioritization" in response.text
    assert 'href="/articles/core"' in response.text
    assert "Low priority item" not in response.text
    assert "newsletter eligible" not in response.text.casefold()
    assert "approved" not in response.text.casefold()


def test_newsletter_selection_uses_phase_3_include_and_exclude_rules(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "ready-core": {
                "id": "ready-core",
                "title": "Ready Core included",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Core summary.",
                "recommendation": "Core",
            },
            "ready-useful": {
                "id": "ready-useful",
                "title": "Ready Useful included",
                "topic": "FinOps",
                "summary_status": "ready",
                "summary": "Useful summary.",
                "recommendation": "Useful",
            },
            "legacy-core": {
                "id": "legacy-core",
                "title": "Legacy Core included",
                "topic": "ProductObservation",
                "summary": "Legacy Core summary.",
                "recommendation": "Core",
            },
            "legacy-useful": {
                "id": "legacy-useful",
                "title": "Legacy Useful included",
                "topic": "Security",
                "summary": "Legacy Useful summary.",
                "recommendation": "Useful",
            },
            "failed-core": {
                "id": "failed-core",
                "title": "Failed Core excluded",
                "summary_status": "failed",
                "summary": "Failed summary.",
                "recommendation": "Core",
            },
            "to-extract-core": {
                "id": "to-extract-core",
                "title": "To Extract Core excluded",
                "summary_status": "to_extract",
                "summary": "Draft summary.",
                "recommendation": "Core",
            },
            "ready-exclude": {
                "id": "ready-exclude",
                "title": "Ready Exclude excluded",
                "summary_status": "ready",
                "summary": "Excluded summary.",
                "recommendation": "Exclude",
            },
            "ready-background": {
                "id": "ready-background",
                "title": "Ready Background excluded",
                "summary_status": "ready",
                "summary": "Background summary.",
                "recommendation": "Background",
            },
            "missing-summary": {
                "id": "missing-summary",
                "title": "Missing Summary excluded",
                "summary_status": "ready",
                "recommendation": "Core",
            },
            "empty-summary": {
                "id": "empty-summary",
                "title": "Empty Summary excluded",
                "summary_status": "ready",
                "summary": "   ",
                "recommendation": "Useful",
            },
            "legacy-missing-summary": {
                "id": "legacy-missing-summary",
                "title": "Legacy Missing Summary excluded",
                "recommendation": "Core",
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current")

    assert response.status_code == 200
    assert "Ready Core included" in response.text
    assert "Ready Useful included" in response.text
    assert "Legacy Core included" in response.text
    assert "Legacy Useful included" in response.text
    assert "Failed Core excluded" not in response.text
    assert "To Extract Core excluded" not in response.text
    assert "Ready Exclude excluded" not in response.text
    assert "Ready Background excluded" not in response.text
    assert "Missing Summary excluded" not in response.text
    assert "Empty Summary excluded" not in response.text
    assert "Legacy Missing Summary excluded" not in response.text
    assert "- article_count: 4" in response.text


def test_newsletter_selection_sorts_by_recommendation_processed_time_and_score(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "useful-newest": {
                "id": "useful-newest",
                "title": "Useful newest",
                "topic": "ProductObservation",
                "summary_status": "ready",
                "summary": "Useful summary.",
                "recommendation": "Useful",
                "last_processed_at": "2026-05-31T12:00:00",
                "ranking_score": 100,
            },
            "core-older": {
                "id": "core-older",
                "title": "Core older",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Core older summary.",
                "recommendation": "Core",
                "last_processed_at": "2026-05-30T12:00:00",
                "ranking_score": 50,
            },
            "core-newer": {
                "id": "core-newer",
                "title": "Core newer",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Core newer summary.",
                "recommendation": "Core",
                "last_processed_at": "2026-05-31T08:00:00",
                "ranking_score": 10,
            },
            "core-tie-low": {
                "id": "core-tie-low",
                "title": "Core same time low score",
                "topic": "FinOps",
                "summary_status": "ready",
                "summary": "Core low summary.",
                "recommendation": "Core",
                "last_processed_at": "2026-05-29T08:00:00",
                "ranking_score": 20,
            },
            "core-score-only": {
                "id": "core-score-only",
                "title": "Core same time score only",
                "topic": "FinOps",
                "summary_status": "ready",
                "summary": "Core score only summary.",
                "recommendation": "Core",
                "last_processed_at": "2026-05-29T08:00:00",
                "score": 999,
            },
            "core-tie-high": {
                "id": "core-tie-high",
                "title": "Core same time high score",
                "topic": "FinOps",
                "summary_status": "ready",
                "summary": "Core high summary.",
                "recommendation": "Core",
                "last_processed_at": "2026-05-29T08:00:00",
                "ranking_score": 80,
            },
            "core-missing-sort-fields": {
                "id": "core-missing-sort-fields",
                "title": "Core missing sort fields",
                "topic": "ProductObservation",
                "summary_status": "ready",
                "summary": "Core missing sort summary.",
                "recommendation": "Core",
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current")
    preview = markdown_preview_markup(response.text)

    assert response.status_code == 200
    assert preview.index("Core newer") < preview.index("Core older")
    assert preview.index("Core older") < preview.index("Core same time high score")
    assert preview.index("Core same time high score") < preview.index(
        "Core same time low score"
    )
    assert preview.index("Core same time low score") < preview.index(
        "Core same time score only"
    )
    assert preview.index("Core same time score only") < preview.index(
        "Core missing sort fields"
    )
    assert preview.index("Core missing sort fields") < preview.index(
        "Useful newest"
    )


def test_newsletter_selection_applies_total_and_topic_limits(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    articles = {}
    for topic in ["AI", "FinOps", "ProductObservation", "Security"]:
        for index in range(1, 5):
            article_id = f"{topic}-{index}"
            articles[article_id] = {
                "id": article_id,
                "title": f"{topic} article {index}",
                "topic": topic,
                "summary_status": "ready",
                "summary": f"{topic} summary {index}.",
                "recommendation": "Core",
                "last_processed_at": f"2026-05-{index + 20:02d}T10:00:00",
                "ranking_score": index,
            }
    write_json(knowledge_path, articles)
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current")
    preview = markdown_preview_markup(response.text)

    assert response.status_code == 200
    assert "- article_count: 10" in response.text
    assert preview.count("AI article") <= 3
    assert preview.count("FinOps article") <= 3
    assert preview.count("ProductObservation article") <= 3
    assert preview.count("Security article") <= 3
    assert preview.count("## ") == 10


def test_newsletter_page_empty_state_uses_weekly_brief_language(
    tmp_path,
    monkeypatch,
):
    client = newsletter_client(
        monkeypatch,
        tmp_path / "articles_knowledge.json",
        tmp_path / "newsletter",
    )

    response = client.get("/newsletter/current")

    assert response.status_code == 200
    assert "No high-signal articles available for this week yet." in response.text
    assert "No brief candidates" not in response.text
    assert "No eligible articles" not in response.text


def test_newsletter_page_topic_filter(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "finops": {
                "id": "finops",
                "title": "FinOps brief item",
                "topic": "FinOps",
                "summary_status": "ready",
                "summary": "FinOps summary.",
                "recommendation": "Core",
            },
            "ai": {
                "id": "ai",
                "title": "AI brief item",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "AI summary.",
                "recommendation": "Core",
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current?topic=FinOps")

    assert response.status_code == 200
    assert "FinOps brief item" in response.text
    assert "AI brief item" not in response.text
    assert "- topic: FinOps" in response.text


def test_newsletter_page_does_not_fallback_to_available_articles(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article": {
                "id": "article",
                "title": "Available article",
                "score": 12,
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter/current")

    assert response.status_code == 200
    assert "Available article" not in response.text
    assert "- article_count: 0" in response.text
    assert "No high-signal articles available for this week yet." in response.text


def test_newsletter_export_writes_markdown_file(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    output_dir = tmp_path / "newsletter"
    write_json(
        knowledge_path,
        {
            "article": {
                "id": "article",
                "url": "https://example.com/article",
                "title": "Exported article",
                "topic": "FinOps",
                "source": "Example",
                "summary_status": "ready",
                "summary": "Export summary.",
                "use_case": "Weekly briefing",
                "problem_solved": "Manual copy-paste",
                "recommendation": "Core",
                "newsletter_status": "not_included",
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, output_dir)

    response = client.post("/newsletter/export", data={"topic": "FinOps"})
    output_path = output_dir / "weekly_brief_finops.md"
    old_output_path = output_dir / "newsletter_draft_finops.md"
    markdown = output_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "Weekly brief exported." in response.text
    assert str(output_path) in response.text
    assert output_path.exists()
    assert not old_output_path.exists()
    assert "newsletter_draft_finops.md" not in response.text
    assert "# Weekly Brief" in markdown
    assert "- topic: FinOps" in markdown
    assert "- generated_at:" in markdown
    assert "- article_count: 1" in markdown
    assert "## 1. Exported article" in markdown
    assert "- recommendation: Core" in markdown
    assert "Export summary." in markdown
    assert "Weekly briefing" in markdown
    assert "Manual copy-paste" in markdown
    assert "- source: Example" in markdown
    assert "- url: https://example.com/article" in markdown


def test_newsletter_export_uses_phase_3_selection_rules(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    output_dir = tmp_path / "newsletter"
    write_json(
        knowledge_path,
        {
            "eligible": {
                "id": "eligible",
                "title": "Eligible export article",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Eligible summary.",
                "recommendation": "Useful",
            },
            "failed": {
                "id": "failed",
                "title": "Failed export article",
                "topic": "AI",
                "summary_status": "failed",
                "summary": "Failed summary.",
                "recommendation": "Core",
            },
            "to-extract": {
                "id": "to-extract",
                "title": "To Extract export article",
                "topic": "AI",
                "summary_status": "to_extract",
                "summary": "To extract summary.",
                "recommendation": "Core",
            },
            "exclude": {
                "id": "exclude",
                "title": "Exclude export article",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Exclude summary.",
                "recommendation": "Exclude",
            },
            "background": {
                "id": "background",
                "title": "Background export article",
                "topic": "AI",
                "summary_status": "ready",
                "summary": "Background summary.",
                "recommendation": "Background",
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, output_dir)

    response = client.post("/newsletter/export", data={"topic": "AI"})
    markdown = (output_dir / "weekly_brief_ai.md").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "Eligible export article" in markdown
    assert "Failed export article" not in markdown
    assert "To Extract export article" not in markdown
    assert "Exclude export article" not in markdown
    assert "Background export article" not in markdown
    assert "- article_count: 1" in markdown


def test_newsletter_export_without_eligible_articles_writes_empty_state(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    output_dir = tmp_path / "newsletter"
    write_json(
        knowledge_path,
        {
            "failed": {
                "id": "failed",
                "title": "Failed export article",
                "summary_status": "failed",
                "summary": "Failed summary.",
                "recommendation": "Core",
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, output_dir)

    response = client.post("/newsletter/export", data={"topic": ""})
    markdown = (output_dir / "weekly_brief_all.md").read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "Weekly brief exported." in response.text
    assert "- article_count: 0" in markdown
    assert "No high-signal articles available for this week yet." in markdown
    assert "Failed export article" not in markdown


def test_newsletter_export_does_not_update_newsletter_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article": {
                "id": "article",
                "title": "Do not mutate",
                "newsletter_status": "not_included",
                "custom_field": {"keep": True},
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.post("/newsletter/export", data={"topic": ""})
    persisted = read_json(knowledge_path)["article"]

    assert response.status_code == 200
    assert persisted["newsletter_status"] == "not_included"
    assert persisted["custom_field"] == {"keep": True}
