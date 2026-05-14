import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path


def load_processed_history(path: str) -> dict:
    history_path = Path(path)

    if not history_path.exists():
        return {}

    try:
        with history_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Warning: Could not parse history file: {history_path}")
        return {}


def save_processed_history(path: str, history: dict) -> None:
    history_path = Path(path)
    history_path.parent.mkdir(parents=True, exist_ok=True)

    with history_path.open("w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=2)


def generate_content_hash(content: str) -> str:
    if not content:
        return ""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def get_today_string() -> str:
    return datetime.today().strftime("%Y-%m-%d")


def is_published_date_old(published_date: str, lookback_days: int) -> bool:
    if not published_date:
        return False

    try:
        published = datetime.strptime(published_date[:10], "%Y-%m-%d")
    except ValueError:
        return False

    oldest_allowed = datetime.today() - timedelta(days=lookback_days)
    return published < oldest_allowed


def determine_freshness_status(
    article: dict,
    history: dict,
    lookback_days: int
) -> str:
    url = article.get("url", "")

    if not url:
        return "unknown"

    previous_article = history.get(url)
    content_hash = article.get("content_hash", "")

    if not previous_article:
        return "new"

    if is_published_date_old(article.get("published_date", ""), lookback_days):
        return "old"

    previous_hash = previous_article.get("content_hash", "")

    if not content_hash:
        return "unknown"

    if not previous_hash:
        return "updated"

    if content_hash != previous_hash:
        return "updated"

    return "repeated"


def update_processed_history(
    article: dict,
    history: dict,
    freshness_status: str
) -> dict:
    url = article.get("url", "")

    if not url:
        return history

    today = get_today_string()
    previous_article = history.get(url, {})

    first_seen = previous_article.get("first_seen", today)
    seen_count = previous_article.get("seen_count", 0) + 1
    content_hash = article.get("content_hash", "")

    if not content_hash:
        content_hash = previous_article.get("content_hash", "")

    history[url] = {
        "title": article.get("title", ""),
        "url": url,
        "source": article.get("source", ""),
        "source_category": article.get("source_category", ""),
        "source_type": article.get("source_type", "rss"),
        "web_mode": article.get("web_mode"),
        "topic": article.get("topic", ""),
        "published_date": article.get("published_date", ""),
        "first_seen": first_seen,
        "last_seen": today,
        "content_hash": content_hash,
        "seen_count": seen_count,
        "last_freshness_status": freshness_status
    }

    return history
