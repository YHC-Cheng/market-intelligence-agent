import json

from web.repositories.json_knowledge_repository import JsonKnowledgeRepository
from web.services.article_processing import ArticleProcessingService


LONG_CONTENT = (
    "This is a detailed market intelligence article with enough extracted "
    "content to pass the minimal quality gate. It discusses product strategy, "
    "customer use cases, operating constraints, and measurable business impact."
)


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def extracted_article(**overrides):
    article = {
        "url": "https://example.com/article",
        "title": "Extracted article",
        "content": LONG_CONTENT,
        "content_length": len(LONG_CONTENT),
        "extraction_status": "success",
        "canonical_url": "https://example.com/article",
    }
    article.update(overrides)
    return article


class FakeProvider:
    def __init__(self, summary=None, ranking=None):
        self.summary = summary or {
            "summary": "Useful generated summary.",
            "analysis": {"market_signal": "strong"},
            "key_points": ["Point one"],
            "why_it_matters": "It matters.",
        }
        self.ranking = ranking or {
            "relevance": 5,
            "use_case_clarity": 5,
            "problem_solution_fit": 5,
            "actionability": 5,
            "credibility_novelty": 5,
            "use_case": "Planning",
            "problem_solved": "Prioritization",
        }

    def summarize_article(self, article):
        return self.summary

    def rank_article(self, article):
        return self.ranking


def service(repository, extractor=None, provider=None):
    return ArticleProcessingService(
        repository,
        extractor=extractor or (lambda article: extracted_article()),
        llm_provider=provider or FakeProvider(),
        now_fn=lambda: "2026-05-31T10:00:00",
    )


def test_process_article_success_updates_summary_and_ranking(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
                "title": "Manual article",
                "summary_status": "to_extract",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    result = service(repository).process_article("article-1")
    persisted = read_json(knowledge_path)["article-1"]

    assert result.success is True
    assert persisted["summary_status"] == "ready"
    assert persisted["summary"] == "Useful generated summary."
    assert persisted["analysis"] == {"market_signal": "strong"}
    assert persisted["recommendation"] == "Core"
    assert persisted["ranking_score"] == 100.0
    assert persisted["failure_reason"] is None
    assert persisted["failure_message"] is None
    assert persisted["last_processed_at"] == "2026-05-31T10:00:00"


def test_process_article_extraction_failure_marks_failed(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
                "summary": "Old summary",
                "analysis": {"old": True},
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    result = service(
        repository,
        extractor=lambda article: {"extraction_status": "failed", "content": ""},
    ).process_article("article-1")
    persisted = read_json(knowledge_path)["article-1"]

    assert result.success is False
    assert persisted["summary_status"] == "failed"
    assert persisted["failure_reason"] == "extraction_failed"
    assert persisted["summary"] is None
    assert persisted["analysis"] is None
    assert persisted["last_processed_at"] == "2026-05-31T10:00:00"


def test_process_article_content_quality_failure_marks_failed(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    result = service(
        repository,
        extractor=lambda article: extracted_article(content="too short"),
    ).process_article("article-1")
    persisted = read_json(knowledge_path)["article-1"]

    assert result.success is False
    assert persisted["summary_status"] == "failed"
    assert persisted["failure_reason"] == "content_quality_failed"
    assert persisted["summary"] is None
    assert persisted["analysis"] is None


def test_process_article_llm_failure_marks_failed(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
            }
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)
    provider = FakeProvider(summary={"summary": "", "error": "LLM unavailable"})

    result = service(repository, provider=provider).process_article("article-1")
    persisted = read_json(knowledge_path)["article-1"]

    assert result.success is False
    assert persisted["summary_status"] == "failed"
    assert persisted["failure_reason"] == "llm_summary_failed"
    assert persisted["summary"] is None
    assert persisted["analysis"] is None
    assert persisted["last_processed_at"] == "2026-05-31T10:00:00"


def test_process_article_canonical_duplicate_marks_current_failed(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "existing": {
                "id": "existing",
                "url": "https://example.com/existing",
                "canonical_url": "https://example.com/canonical",
                "summary_status": "ready",
            },
            "current": {
                "id": "current",
                "url": "https://example.com/current",
                "summary_status": "to_extract",
            },
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    result = service(
        repository,
        extractor=lambda article: extracted_article(
            url="https://example.com/current",
            canonical_url="https://example.com/canonical",
        ),
    ).process_article("current")
    persisted = read_json(knowledge_path)

    assert result.success is False
    assert persisted["current"]["summary_status"] == "failed"
    assert persisted["current"]["failure_reason"] == "duplicate_after_extraction"
    assert persisted["current"]["duplicate_of_article_id"] == "existing"
    assert persisted["existing"]["summary_status"] == "ready"


def test_process_article_unknown_exception_marks_failed(tmp_path):
    class BrokenFindRepository(JsonKnowledgeRepository):
        def find_by_canonical_url(self, canonical_url):
            raise RuntimeError("unexpected duplicate lookup failure")

    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
            }
        },
    )
    repository = BrokenFindRepository(knowledge_path)

    result = service(repository).process_article("article-1")
    persisted = read_json(knowledge_path)["article-1"]

    assert result.success is False
    assert persisted["summary_status"] == "failed"
    assert persisted["failure_reason"] == "unknown_error"
    assert persisted["summary"] is None
    assert persisted["analysis"] is None


def test_process_article_repository_write_failure_returns_result(tmp_path):
    class BrokenUpdateRepository(JsonKnowledgeRepository):
        def update_article(self, article_id, updates):
            raise OSError("cannot write repository")

    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "article-1": {
                "id": "article-1",
                "url": "https://example.com/article",
            }
        },
    )
    repository = BrokenUpdateRepository(knowledge_path)

    result = service(repository).process_article("article-1")

    assert result.success is False
    assert result.failure_reason == "repository_write_failed"
    assert result.failure_message == "cannot write repository"


def test_recommendation_mapping_excludes_background_and_unknown(tmp_path):
    knowledge_path = tmp_path / "articles_knowledge.json"
    write_json(
        knowledge_path,
        {
            "background": {
                "id": "background",
                "url": "https://example.com/background",
            },
            "unknown": {
                "id": "unknown",
                "url": "https://example.com/unknown",
            },
        },
    )
    repository = JsonKnowledgeRepository(knowledge_path)

    service(
        repository,
        extractor=lambda article: extracted_article(
            url=article["url"],
            canonical_url=article["url"],
        ),
        provider=FakeProvider(ranking={"score": 60, "recommendation": "Background"}),
    ).process_article("background")
    service(
        repository,
        extractor=lambda article: extracted_article(
            url=article["url"],
            canonical_url=article["url"],
        ),
        provider=FakeProvider(ranking={"score": 99, "recommendation": "Surprise"}),
    ).process_article("unknown")
    persisted = read_json(knowledge_path)

    assert persisted["background"]["recommendation"] == "Exclude"
    assert persisted["unknown"]["recommendation"] == "Exclude"
