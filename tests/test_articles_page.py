import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def article_client(monkeypatch, knowledge_path):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    return TestClient(app_module.app)


def test_articles_page_handles_empty_repository(tmp_path, monkeypatch):
    client = article_client(monkeypatch, tmp_path / "missing_articles.json")

    response = client.get("/articles")

    assert response.status_code == 200
    assert "Knowledge Explorer" in response.text
    assert "No articles found" in response.text


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

    response = client.get("/articles")

    assert response.status_code == 200
    assert "Cloud cost control" in response.text
    assert "FinOps" in response.text
    assert "Example Blog" in response.text
    assert "88.0" in response.text
    assert "approved" in response.text
    assert "Yes" in response.text
    assert 'href="https://example.com/cloud-costs"' in response.text


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

    response = client.get("/articles?topic=FinOps")

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

    response = client.get("/articles?keyword=cloud")

    assert response.status_code == 200
    assert "Cloud planning guide" in response.text
    assert "Security update" not in response.text
