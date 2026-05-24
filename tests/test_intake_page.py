import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def intake_client(monkeypatch, knowledge_path):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    return TestClient(app_module.app)


def test_intake_page_displays_form(tmp_path, monkeypatch):
    client = intake_client(monkeypatch, tmp_path / "articles_knowledge.json")

    response = client.get("/intake")

    assert response.status_code == 200
    assert "Add Article" in response.text
    assert "Article URL" in response.text
    assert "Cancel" in response.text
    assert 'name="url"' in response.text
    assert 'name="topic"' in response.text
    assert 'name="note"' in response.text
    assert "FinOps" in response.text


def test_intake_post_creates_manual_article(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    client = intake_client(monkeypatch, knowledge_path)

    response = client.post(
        "/intake",
        data={
            "url": " https://example.com/manual/ ",
            "topic": "FinOps",
            "note": "Review this source.",
        },
    )
    persisted = read_json(knowledge_path)
    article = persisted["https://example.com/manual"]

    assert response.status_code == 200
    assert "Manual article created." in response.text
    assert "https://example.com/manual/" in response.text
    assert article["canonical_url"] == "https://example.com/manual"
    assert article["url"] == "https://example.com/manual/"
    assert article["title"] == "https://example.com/manual/"
    assert article["topic"] == "FinOps"
    assert article["note"] == "Review this source."
    assert article["source"] == "manual"
    assert article["ingestion_type"] == "manual"
    assert article["review_status"] == "unreviewed"
    assert article["newsletter_eligible"] is False
    assert article["newsletter_status"] == "not_included"
    assert article["extraction_status"] == "not_started"
    assert article["analysis_status"] == "not_started"
    assert "created_at" in article
    assert "updated_at" in article


def test_intake_post_empty_url_shows_error_without_creating_article(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    client = intake_client(monkeypatch, knowledge_path)

    response = client.post(
        "/intake",
        data={"url": " ", "topic": "AI", "note": "No URL."},
    )

    assert response.status_code == 400
    assert "URL is required." in response.text
    assert not knowledge_path.exists()


def test_intake_post_invalid_topic_shows_error_without_creating_article(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    client = intake_client(monkeypatch, knowledge_path)

    response = client.post(
        "/intake",
        data={
            "url": "https://example.com/manual",
            "topic": "Security",
            "note": "Wrong topic.",
        },
    )

    assert response.status_code == 400
    assert "Choose a valid topic." in response.text
    assert not knowledge_path.exists()


def test_intake_post_duplicate_url_shows_warning_without_creating_second_article(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/manual": {
                "url": "https://example.com/manual",
                "canonical_url": "https://example.com/manual",
                "title": "Existing manual article",
                "topic": "AI",
                "custom_field": {"keep": True},
            }
        },
    )
    client = intake_client(monkeypatch, knowledge_path)

    response = client.post(
        "/intake",
        data={
            "url": " https://example.com/manual/ ",
            "topic": "FinOps",
            "note": "Duplicate.",
        },
    )
    persisted = read_json(knowledge_path)

    assert response.status_code == 200
    assert "already in the knowledge repository" in response.text
    assert "Open existing article" in response.text
    assert 'href="/articles/https%3A%2F%2Fexample.com%2Fmanual"' in response.text
    assert len(persisted) == 1
    assert persisted["https://example.com/manual"]["title"] == "Existing manual article"
    assert persisted["https://example.com/manual"]["custom_field"] == {"keep": True}
