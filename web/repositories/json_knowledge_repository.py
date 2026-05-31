import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


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

    def find_by_normalized_url(self, normalized_url):
        if not normalized_url:
            return None

        for key, article in self._iter_articles(self._read_json()):
            if article.get("normalized_url") == normalized_url:
                return self._with_runtime_defaults(article, key)

        return None

    def find_by_canonical_url(self, canonical_url):
        if not canonical_url:
            return None

        for key, article in self._iter_articles(self._read_json()):
            if article.get("canonical_url") == canonical_url:
                return self._with_runtime_defaults(article, key)

        return None

    def update_article(self, article_id, updates):
        raw_data = self._read_json()
        found = self._find_article(raw_data, article_id)

        if found is None:
            return None

        key, article = found
        article.update(deepcopy(updates or {}))
        article["updated_at"] = self._now()

        self._replace_article(raw_data, key, article)
        self._write_json(raw_data)
        return self._with_runtime_defaults(article, key)

    def delete_article(self, article_id):
        raw_data = self._read_json()
        found = self._find_article(raw_data, article_id)

        if found is None:
            return None

        key, article = found
        self._delete_article(raw_data, key, article)
        self._write_json(raw_data)
        return self._with_runtime_defaults(article, key)

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

    def update_article_recommendation(self, article_id, recommendation):
        raw_data = self._read_json()
        found = self._find_article(raw_data, article_id)

        if found is None:
            return None

        key, article = found
        article["recommendation"] = recommendation
        article["updated_at"] = self._now()

        self._replace_article(raw_data, key, article)
        self._write_json(raw_data)
        return self._with_runtime_defaults(article, key)

    def create_manual_article(self, url, topic, note, normalized_url=None):
        normalized_url = normalized_url or self.normalize_url(url)
        canonical_url = normalized_url
        raw_data = self._read_json()

        for key, article in self._iter_articles(raw_data):
            existing_normalized_url = article.get("normalized_url")
            if not existing_normalized_url:
                existing_normalized_url = self.canonicalize_url(article.get("url", ""))

            if existing_normalized_url == normalized_url:
                return {
                    "article": self._with_runtime_defaults(article, key),
                    "duplicate": True,
                }

        now = self._now()
        article = {
            "id": canonical_url,
            "url": url.strip(),
            "normalized_url": normalized_url,
            "canonical_url": canonical_url,
            "title": url.strip(),
            "topic": topic,
            "source": "manual",
            "source_type": "manual",
            "note": note,
            "ingestion_type": "manual",
            "review_status": "unreviewed",
            "newsletter_eligible": False,
            "newsletter_status": "not_included",
            "extraction_status": "not_started",
            "analysis_status": "not_started",
            "summary_status": "to_extract",
            "failure_reason": None,
            "failure_message": None,
            "created_at": now,
            "updated_at": now,
        }

        self._append_article(raw_data, article)
        self._write_json(raw_data)
        return {"article": article, "duplicate": False}

    @staticmethod
    def canonicalize_url(url):
        return JsonKnowledgeRepository.normalize_url(url)

    @staticmethod
    def normalize_url(url):
        cleaned_url = (url or "").strip()
        parsed_url = urlsplit(cleaned_url)

        scheme = parsed_url.scheme.lower()
        hostname = parsed_url.hostname
        if not scheme or hostname is None:
            return cleaned_url.rstrip("/")

        host = hostname.lower()
        try:
            port = parsed_url.port
        except ValueError:
            port = None

        netloc = host
        if ":" in host and not host.startswith("["):
            netloc = f"[{host}]"

        if parsed_url.username:
            userinfo = parsed_url.username
            if parsed_url.password:
                userinfo = f"{userinfo}:{parsed_url.password}"
            netloc = f"{userinfo}@{netloc}"

        if port and not (
            (scheme == "http" and port == 80)
            or (scheme == "https" and port == 443)
        ):
            netloc = f"{netloc}:{port}"

        path = parsed_url.path
        if path != "/":
            path = path.rstrip("/")

        return urlunsplit((scheme, netloc, path, parsed_url.query, ""))

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

    def _delete_article(self, raw_data, key, article):
        if isinstance(raw_data, list):
            raw_data[:] = [
                existing_article
                for existing_article in raw_data
                if existing_article is not article
            ]
            return

        raw_data.pop(key, None)

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
