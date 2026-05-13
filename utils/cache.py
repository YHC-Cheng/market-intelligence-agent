import json
from pathlib import Path


def load_json_cache(path: str) -> dict:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if not cache_path.exists():
        save_json_cache(path, {})
        return {}

    try:
        with cache_path.open("r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return {}


def save_json_cache(path: str, cache: dict) -> None:
    cache_path = Path(path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    with cache_path.open("w", encoding="utf-8") as file:
        json.dump(cache, file, indent=2, ensure_ascii=False)


def get_cached_result(cache: dict, url: str):
    return cache.get(url)


def set_cached_result(cache: dict, url: str, value: dict):
    cache[url] = value
