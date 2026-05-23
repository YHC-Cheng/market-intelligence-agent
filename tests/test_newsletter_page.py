import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def newsletter_client(monkeypatch, knowledge_path, output_dir):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    monkeypatch.setattr(app_module, "NEWSLETTER_OUTPUT_DIR", output_dir)
    return TestClient(app_module.app)


def test_newsletter_page_displays_phase_1_7(tmp_path, monkeypatch):
    client = newsletter_client(
        monkeypatch,
        tmp_path / "articles_knowledge.json",
        tmp_path / "newsletter",
    )

    response = client.get("/newsletter")

    assert response.status_code == 200
    assert "Market Intelligence Agent 2.0" in response.text
    assert "Phase 1.7 Newsletter Draft" in response.text
    assert "Phase 2.7" not in response.text
    assert "Markdown preview" in response.text


def test_newsletter_page_only_shows_approved_eligible_articles(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "eligible": {
                "id": "eligible",
                "url": "https://example.com/eligible",
                "title": "Eligible article",
                "topic": "AI",
                "source": "Example",
                "score": 91,
                "summary": "A useful article.",
                "use_case": "Planning",
                "problem_solved": "Prioritization",
                "review_status": "approved",
                "newsletter_eligible": True,
            },
            "not-approved": {
                "id": "not-approved",
                "title": "Not approved article",
                "review_status": "unreviewed",
                "newsletter_eligible": True,
            },
            "not-eligible": {
                "id": "not-eligible",
                "title": "Not eligible article",
                "review_status": "approved",
                "newsletter_eligible": False,
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter")

    assert response.status_code == 200
    assert "Eligible article" in response.text
    assert "A useful article." in response.text
    assert "Planning" in response.text
    assert "Prioritization" in response.text
    assert 'href="https://example.com/eligible"' in response.text
    assert 'href="/articles/eligible"' in response.text
    assert "Not approved article" not in response.text
    assert "Not eligible article" not in response.text


def test_newsletter_page_topic_filter(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "finops": {
                "id": "finops",
                "title": "FinOps newsletter item",
                "topic": "FinOps",
                "review_status": "approved",
                "newsletter_eligible": True,
            },
            "ai": {
                "id": "ai",
                "title": "AI newsletter item",
                "topic": "AI",
                "review_status": "approved",
                "newsletter_eligible": True,
            },
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter?topic=FinOps")

    assert response.status_code == 200
    assert "FinOps newsletter item" in response.text
    assert "AI newsletter item" not in response.text
    assert "<option value=\"FinOps\" selected>" in response.text
    assert "- topic: FinOps" in response.text


def test_newsletter_page_empty_state(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article": {
                "id": "article",
                "title": "Unreviewed article",
                "review_status": "unreviewed",
                "newsletter_eligible": True,
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, tmp_path / "newsletter")

    response = client.get("/newsletter")

    assert response.status_code == 200
    assert "No eligible articles" in response.text
    assert "- article_count: 0" in response.text


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
                "summary": "Export summary.",
                "use_case": "Weekly briefing",
                "problem_solved": "Manual copy-paste",
                "review_status": "approved",
                "newsletter_eligible": True,
                "newsletter_status": "not_included",
            }
        },
    )
    client = newsletter_client(monkeypatch, knowledge_path, output_dir)

    response = client.post("/newsletter/export", data={"topic": "FinOps"})
    output_path = output_dir / "newsletter_draft_finops.md"
    markdown = output_path.read_text(encoding="utf-8")

    assert response.status_code == 200
    assert "Newsletter draft exported." in response.text
    assert str(output_path) in response.text
    assert output_path.exists()
    assert "# Market Intelligence Newsletter Draft" in markdown
    assert "- topic: FinOps" in markdown
    assert "- generated_at:" in markdown
    assert "- article_count: 1" in markdown
    assert "## 1. Exported article" in markdown
    assert "Export summary." in markdown
    assert "Weekly briefing" in markdown
    assert "Manual copy-paste" in markdown
    assert "- source: Example" in markdown
    assert "- url: https://example.com/article" in markdown


def test_newsletter_export_does_not_update_newsletter_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article": {
                "id": "article",
                "title": "Do not mutate",
                "review_status": "approved",
                "newsletter_eligible": True,
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
