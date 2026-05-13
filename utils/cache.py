import json
from datetime import datetime
from pathlib import Path


def sanitize_filename(value: str) -> str:
    safe_characters = []

    for character in value:
        if character.isalnum() or character in ["-", "_"]:
            safe_characters.append(character)
        else:
            safe_characters.append("_")

    safe_name = "".join(safe_characters).strip("_")

    if not safe_name:
        return "default"

    return safe_name


def get_current_week_key() -> str:
    today = datetime.today()
    iso_year, iso_week, _ = today.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def get_cache_paths(topic: str, week_key=None) -> dict:
    if week_key is None:
        week_key = get_current_week_key()

    safe_topic = sanitize_filename(topic)
    cache_folder = Path("data/cache") / safe_topic / week_key

    return {
        "summary": str(cache_folder / "summary_cache.json"),
        "ranking": str(cache_folder / "ranking_cache.json"),
        "report": str(cache_folder / "report_cache.json")
    }


def ensure_cache_file(path: str) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not cache_path.exists():
        with cache_path.open("w", encoding="utf-8") as file:
            json.dump({}, file, indent=2, ensure_ascii=False)


def load_json_cache(path: str) -> dict:
    ensure_cache_file(path)
    cache_path = Path(path)

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except json.JSONDecodeError:
        print(f"Warning: Cache file is not valid JSON: {path}")
        return {}
    except OSError as error:
        print(f"Warning: Could not read cache file {path}: {error}")
        return {}


def save_json_cache(path: str, cache: dict) -> None:
    ensure_cache_file(path)
    cache_path = Path(path)

    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)


def get_cached_result(cache: dict, url: str):
    return cache.get(url)


def set_cached_result(cache: dict, url: str, value: dict):
    cache[url] = value
