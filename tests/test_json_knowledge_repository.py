import json

import pytest

from web.repositories.json_knowledge_repository import JsonKnowledgeRepository


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_load_missing_file_returns_empty_list(tmp_path):
    repository = JsonKnowledgeRepository(tmp_path / "missing.json")

    assert repository.load_articles() == []


def test_load_articles_adds_default_review_fields_in_returned_data(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/article": {
                "url": "https://example.com/article",
                "title": "Example",
            }
        },
    )

    repository = JsonKnowledgeRepository(knowledge_path)
    articles = repository.load_articles()
    persisted = read_json(knowledge_path)

    assert articles[0]["review_status"] == "unreviewed"
    assert articles[0]["newsletter_eligible"] is False
    assert articles[0]["newsletter_status"] == "not_included"
    assert articles[0]["review_note"] == ""
    assert "review_status" not in persisted["https://example.com/article"]


def test_list_articles_filters_by_topic(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/ai": {
                "url": "https://example.com/ai",
                "title": "AI article",
                "topic": "AI",
            },
            "https://example.com/finops": {
                "url": "https://example.com/finops",
                "title": "FinOps article",
                "topic": "FinOps",
            },
        },
    )

    repository = JsonKnowledgeRepository(knowledge_path)
    articles = repository.list_articles(topic="AI")

    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/ai"


def test_list_articles_filters_by_keyword(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/one": {
                "url": "https://example.com/one",
                "title": "Quiet launch",
                "summary": "A cost management workflow for teams.",
                "source": "Example",
            },
            "https://example.com/two": {
                "url": "https://example.com/two",
                "title": "Different story",
                "summary": "Nothing related here.",
                "source": "Another",
            },
        },
    )

    repository = JsonKnowledgeRepository(knowledge_path)
    articles = repository.list_articles(keyword="COST")

    assert len(articles) == 1
    assert articles[0]["url"] == "https://example.com/one"


def test_update_article_review_preserves_unknown_fields(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/article": {
                "url": "https://example.com/article",
                "title": "Example",
                "custom_field": {"keep": True},
            }
        },
    )

    repository = JsonKnowledgeRepository(knowledge_path)
    article = repository.update_article_review(
        "https://example.com/article",
        review_status="approved",
        newsletter_eligible=True,
        review_note="Looks useful.",
    )
    persisted = read_json(knowledge_path)["https://example.com/article"]

    assert article["review_status"] == "approved"
    assert persisted["custom_field"] == {"keep": True}
    assert persisted["newsletter_eligible"] is True
    assert persisted["review_note"] == "Looks useful."
    assert "updated_at" in persisted
    assert "reviewed_at" in persisted


def test_update_article_recommendation_preserves_unknown_fields(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/article": {
                "url": "https://example.com/article",
                "title": "Example",
                "recommendation": "Useful",
                "custom_field": {"keep": True},
            }
        },
    )

    repository = JsonKnowledgeRepository(knowledge_path)
    article = repository.update_article_recommendation(
        "https://example.com/article",
        "Core",
    )
    persisted = read_json(knowledge_path)["https://example.com/article"]

    assert article["recommendation"] == "Core"
    assert persisted["recommendation"] == "Core"
    assert persisted["custom_field"] == {"keep": True}
    assert "updated_at" in persisted


def test_create_manual_article_creates_article(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    repository = JsonKnowledgeRepository(knowledge_path)

    result = repository.create_manual_article(
        " https://example.com/manual/ ",
        "AI",
        "Review this manually.",
    )
    persisted = read_json(knowledge_path)
    article = result["article"]

    assert result["duplicate"] is False
    assert article["canonical_url"] == "https://example.com/manual"
    assert article["normalized_url"] == "https://example.com/manual"
    assert article["title"] == "https://example.com/manual/"
    assert article["source"] == "manual"
    assert article["source_type"] == "manual"
    assert article["ingestion_type"] == "manual"
    assert article["extraction_status"] == "not_started"
    assert article["summary_status"] == "to_extract"
    assert article["failure_reason"] is None
    assert article["failure_message"] is None
    assert "https://example.com/manual" in persisted


@pytest.mark.parametrize(
    ("url", "normalized_url"),
    [
        (" HTTPS://Example.com/Article/ ", "https://example.com/Article"),
        ("https://example.com/article/#section", "https://example.com/article"),
        (
            "https://example.com/article/?utm_source=x",
            "https://example.com/article?utm_source=x",
        ),
        ("http://example.com:80/article", "http://example.com/article"),
        ("https://example.com:443/article", "https://example.com/article"),
    ],
)
def test_normalize_url_applies_phase_3_rules(url, normalized_url):
    assert JsonKnowledgeRepository.normalize_url(url) == normalized_url


def test_find_by_normalized_url_returns_matching_article(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
                "normalized_url": "https://example.com/article",
                "title": "Example",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    article = repository.find_by_normalized_url("https://example.com/article")

    assert article["id"] == "article-1"
    assert article["title"] == "Example"


def test_find_by_canonical_url_returns_matching_article(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article?ref=feed",
                "canonical_url": "https://example.com/article",
                "title": "Example",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    article = repository.find_by_canonical_url("https://example.com/article")

    assert article["id"] == "article-1"
    assert article["title"] == "Example"


def test_find_by_url_methods_handle_missing_values_safely(tmp_path):
    repository = JsonKnowledgeRepository(tmp_path / "missing.json")

    assert repository.find_by_normalized_url("") is None
    assert repository.find_by_normalized_url("https://example.com/missing") is None
    assert repository.find_by_canonical_url(None) is None
    assert repository.find_by_canonical_url("https://example.com/missing") is None


def test_update_article_updates_only_target_article(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Original",
                "summary_status": "to_extract",
            },
            "article-2": {
                "id": "article-2",
                "title": "Keep me",
                "summary_status": "to_extract",
            },
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    article = repository.update_article(
        "article-1",
        {"summary_status": "failed", "failure_reason": "fetch_failed"},
    )
    persisted = read_json(knowledge_path)

    assert article["summary_status"] == "failed"
    assert persisted["article-1"]["summary_status"] == "failed"
    assert persisted["article-1"]["failure_reason"] == "fetch_failed"
    assert persisted["article-1"]["title"] == "Original"
    assert "updated_at" in persisted["article-1"]
    assert persisted["article-2"] == {
        "id": "article-2",
        "title": "Keep me",
        "summary_status": "to_extract",
    }


def test_delete_article_removes_only_target_article(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Delete me",
            },
            "article-2": {
                "id": "article-2",
                "title": "Keep me",
            },
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    deleted_article = repository.delete_article("article-1")
    persisted = read_json(knowledge_path)

    assert deleted_article["id"] == "article-1"
    assert "article-1" not in persisted
    assert persisted == {
        "article-2": {
            "id": "article-2",
            "title": "Keep me",
        }
    }


def test_update_and_delete_article_handle_missing_ids_safely(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "title": "Keep me",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    assert repository.update_article("missing", {"title": "Nope"}) is None
    assert repository.delete_article("missing") is None
    assert read_json(knowledge_path) == {
        "article-1": {
            "id": "article-1",
            "title": "Keep me",
        }
    }


def test_create_manual_article_detects_duplicate_canonical_url(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/manual": {
                "url": "https://example.com/manual",
                "normalized_url": "https://example.com/manual",
                "canonical_url": "https://example.com/manual",
                "title": "Existing",
                "unknown": "keep",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    result = repository.create_manual_article(
        "https://example.com/manual/",
        "AI",
        "Duplicate.",
    )
    persisted = read_json(knowledge_path)

    assert result["duplicate"] is True
    assert result["article"]["title"] == "Existing"
    assert len(persisted) == 1
    assert persisted["https://example.com/manual"]["unknown"] == "keep"
