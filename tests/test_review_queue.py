import json

from fastapi.testclient import TestClient

from web import app as app_module
from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def review_client(monkeypatch, knowledge_path):
    def repository_factory():
        return JsonKnowledgeRepository(knowledge_path)

    monkeypatch.setattr(app_module, "get_knowledge_repository", repository_factory)
    return TestClient(app_module.app)


def test_review_queue_page_displays(tmp_path, monkeypatch):
    client = review_client(monkeypatch, tmp_path / "articles_knowledge.json")

    response = client.get("/review")

    assert response.status_code == 200
    assert "Articles to review" in response.text
    assert 'name="topic"' in response.text
    assert "No articles waiting for review" in response.text


def test_review_queue_only_shows_reviewable_statuses(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "unreviewed": {
                "id": "unreviewed",
                "title": "Unreviewed article",
                "review_status": "unreviewed",
            },
            "needs-fix": {
                "id": "needs-fix",
                "title": "Needs fix article",
                "review_status": "needs_fix",
            },
            "duplicate": {
                "id": "duplicate",
                "title": "Duplicate article",
                "review_status": "duplicate",
            },
            "approved": {
                "id": "approved",
                "title": "Approved article",
                "review_status": "approved",
            },
            "rejected": {
                "id": "rejected",
                "title": "Rejected article",
                "review_status": "rejected",
            },
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.get("/review")

    assert response.status_code == 200
    assert "Unreviewed article" in response.text
    assert "Needs fix article" in response.text
    assert "Duplicate article" in response.text
    assert "Approved article" not in response.text
    assert "Rejected article" not in response.text


def test_review_queue_topic_filter(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "finops": {
                "id": "finops",
                "title": "FinOps article",
                "topic": "FinOps",
                "review_status": "unreviewed",
            },
            "ai": {
                "id": "ai",
                "title": "AI article",
                "topic": "AI",
                "review_status": "unreviewed",
            },
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.get("/review?topic=FinOps")

    assert response.status_code == 200
    assert "FinOps article" in response.text
    assert "AI article" not in response.text
    assert 'value="FinOps"' in response.text


def test_review_queue_approve_action_updates_review_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Approve me",
                "review_status": "unreviewed",
                "custom_field": {"keep": True},
            }
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.post(
        "/review/action",
        data={"article_id": "article-1", "action": "approve"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Review queue updated." in response.text
    assert persisted["review_status"] == "approved"
    assert persisted["custom_field"] == {"keep": True}


def test_review_queue_reject_action_updates_review_status(tmp_path, monkeypatch):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Reject me",
                "review_status": "unreviewed",
            }
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.post(
        "/review/action",
        data={"article_id": "article-1", "action": "reject"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Review queue updated." in response.text
    assert persisted["review_status"] == "rejected"


def test_review_queue_mark_duplicate_action_updates_review_status(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Mark duplicate",
                "review_status": "unreviewed",
            }
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.post(
        "/review/action",
        data={"article_id": "article-1", "action": "mark_duplicate"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Review queue updated." in response.text
    assert persisted["review_status"] == "duplicate"


def test_review_queue_toggle_eligible_action_updates_newsletter_eligible(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Toggle newsletter",
                "review_status": "unreviewed",
                "newsletter_eligible": False,
            }
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    response = client.post(
        "/review/action",
        data={"article_id": "article-1", "action": "toggle_eligible"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert response.status_code == 200
    assert "Review queue updated." in response.text
    assert persisted["newsletter_eligible"] is True


def test_review_queue_invalid_inputs_show_error_without_crashing(
    tmp_path,
    monkeypatch,
):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Do not change",
                "review_status": "unreviewed",
            }
        },
    )
    client = review_client(monkeypatch, knowledge_path)

    missing_response = client.post(
        "/review/action",
        data={"article_id": "missing", "action": "approve"},
    )
    invalid_action_response = client.post(
        "/review/action",
        data={"article_id": "article-1", "action": "explode"},
    )
    persisted = read_json(knowledge_path)["article-1"]

    assert missing_response.status_code == 200
    assert "Article not found." in missing_response.text
    assert invalid_action_response.status_code == 200
    assert "Invalid review action." in invalid_action_response.text
    assert persisted["review_status"] == "unreviewed"
