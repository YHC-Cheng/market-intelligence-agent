import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_KNOWLEDGE_PATH = REPO_ROOT / "data" / "knowledge" / "articles_knowledge.json"

DEFAULT_REVIEW_FIELDS = {
    "review_status": "unreviewed",
    "newsletter_eligible": False,
    "newsletter_status": "not_included",
    "review_note": "",
}

REVIEWED_STATUSES = {"approved", "rejected", "needs_fix", "duplicate"}


class JsonKnowledgeRepository:
    def __init__(self, knowledge_path=None):
        self.knowledge_path = Path(knowledge_path or DEFAULT_KNOWLEDGE_PATH)

    def load_articles(self):
        if not self.knowledge_path.exists():
            return []

        raw_data = self._read_json()
        return [
            self._with_runtime_defaults(article, key)
            for key, article in self._iter_articles(raw_data)
        ]

    def save_articles(self, articles):
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)

        existing_data = self._read_json() if self.knowledge_path.exists() else {}
        if isinstance(existing_data, list):
            data = [deepcopy(article) for article in articles]
        else:
            data = {}
            for article in articles:
                article_copy = deepcopy(article)
                key = self._storage_key(article_copy)
                data[key] = article_copy

        with self.knowledge_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def list_articles(
        self,
        topic=None,
        keyword=None,
        review_status=None,
        newsletter_eligible=None,
    ):
        articles = self.load_articles()

        if topic is not None:
            articles = [
                article for article in articles
                if article.get("topic") == topic
            ]

        if review_status is not None:
            articles = [
                article for article in articles
                if article.get("review_status") == review_status
            ]

        if newsletter_eligible is not None:
            articles = [
                article for article in articles
                if article.get("newsletter_eligible") is newsletter_eligible
            ]

        if keyword:
            normalized_keyword = keyword.casefold()
            articles = [
                article for article in articles
                if self._matches_keyword(article, normalized_keyword)
            ]

        return articles

    def get_article(self, article_id):
        for article in self.load_articles():
            if self._matches_article_id(article, article_id):
                return article

        return None

    def update_article_review(
        self,
        article_id,
        review_status=None,
        newsletter_eligible=None,
        review_note=None,
    ):
        raw_data = self._read_json()
        found = self._find_article(raw_data, article_id)

        if found is None:
            return None

        key, article = found
        article["updated_at"] = self._now()

        if review_status is not None:
            article["review_status"] = review_status
            if review_status in REVIEWED_STATUSES:
                article["reviewed_at"] = article["updated_at"]

        if newsletter_eligible is not None:
            article["newsletter_eligible"] = newsletter_eligible

        if review_note is not None:
            article["review_note"] = review_note

        self._replace_article(raw_data, key, article)
        self._write_json(raw_data)
        return self._with_runtime_defaults(article, key)

    def create_manual_article(self, url, topic, note):
        canonical_url = self.canonicalize_url(url)
        raw_data = self._read_json()

        for key, article in self._iter_articles(raw_data):
            existing_canonical_url = article.get("canonical_url")
            if not existing_canonical_url:
                existing_canonical_url = self.canonicalize_url(article.get("url", ""))

            if existing_canonical_url == canonical_url:
                return {
                    "article": self._with_runtime_defaults(article, key),
                    "duplicate": True,
                }

        now = self._now()
        article = {
            "id": canonical_url,
            "url": url.strip(),
            "canonical_url": canonical_url,
            "title": url.strip(),
            "topic": topic,
            "source": "manual",
            "note": note,
            "ingestion_type": "manual",
            "review_status": "unreviewed",
            "newsletter_eligible": False,
            "newsletter_status": "not_included",
            "extraction_status": "not_started",
            "analysis_status": "not_started",
            "created_at": now,
            "updated_at": now,
        }

        self._append_article(raw_data, article)
        self._write_json(raw_data)
        return {"article": article, "duplicate": False}

    @staticmethod
    def canonicalize_url(url):
        return (url or "").strip().rstrip("/")

    def _read_json(self):
        if not self.knowledge_path.exists():
            return {}

        with self.knowledge_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write_json(self, data):
        self.knowledge_path.parent.mkdir(parents=True, exist_ok=True)
        with self.knowledge_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _iter_articles(self, raw_data):
        if isinstance(raw_data, dict):
            for key, article in raw_data.items():
                if isinstance(article, dict):
                    yield key, article
            return

        if isinstance(raw_data, list):
            for article in raw_data:
                if isinstance(article, dict):
                    yield self._storage_key(article), article

    def _with_runtime_defaults(self, article, key=None):
        article_copy = deepcopy(article)
        article_copy.setdefault("id", self._article_id(article_copy, key))

        for field, default_value in DEFAULT_REVIEW_FIELDS.items():
            article_copy.setdefault(field, default_value)

        return article_copy

    def _find_article(self, raw_data, article_id):
        for key, article in self._iter_articles(raw_data):
            if self._matches_article_id(article, article_id, key):
                return key, article

        return None

    def _replace_article(self, raw_data, key, article):
        if isinstance(raw_data, list):
            for index, existing_article in enumerate(raw_data):
                if existing_article is article:
                    raw_data[index] = article
                    return
            return

        raw_data[key] = article

    def _append_article(self, raw_data, article):
        if isinstance(raw_data, list):
            raw_data.append(article)
            return

        raw_data[self._storage_key(article)] = article

    def _storage_key(self, article):
        return self._article_id(article, article.get("url", ""))

    def _article_id(self, article, key=None):
        return (
            article.get("id")
            or article.get("canonical_url")
            or article.get("url")
            or key
            or ""
        )

    def _matches_article_id(self, article, article_id, key=None):
        normalized_article_id = str(article_id)
        candidates = {
            str(candidate)
            for candidate in [
                article.get("id"),
                article.get("canonical_url"),
                article.get("url"),
                key,
            ]
            if candidate
        }
        return normalized_article_id in candidates

    def _matches_keyword(self, article, normalized_keyword):
        fields = ["title", "summary", "source", "url"]
        return any(
            normalized_keyword in str(article.get(field, "")).casefold()
            for field in fields
        )

    def _now(self):
        return datetime.now().replace(microsecond=0).isoformat()
