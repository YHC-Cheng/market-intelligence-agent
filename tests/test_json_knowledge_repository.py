import json

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
    assert article["title"] == "https://example.com/manual/"
    assert article["source"] == "manual"
    assert article["ingestion_type"] == "manual"
    assert article["extraction_status"] == "not_started"
    assert "https://example.com/manual" in persisted


def test_create_manual_article_detects_duplicate_canonical_url(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "https://example.com/manual": {
                "url": "https://example.com/manual",
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
