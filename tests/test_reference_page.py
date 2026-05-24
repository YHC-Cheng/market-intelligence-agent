import json

from fastapi.testclient import TestClient

from web import app as app_module


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def sidebar_markup(response_text):
    start = response_text.index('<nav class="sidebar-nav">')
    end = response_text.index("</nav>", start)
    return response_text[start:end]


def reference_client(monkeypatch, keywords_path, rss_sources=None, sources=None):
    monkeypatch.setattr(app_module, "KEYWORDS_CONFIG_PATH", keywords_path)
    if rss_sources is not None:
        monkeypatch.setattr(app_module, "RSS_SOURCES_BY_TOPIC", rss_sources)
    if sources is not None:
        monkeypatch.setattr(app_module, "SOURCES", sources)
    return TestClient(app_module.app)


def test_reference_page_uses_shared_shell_and_sidebar(tmp_path, monkeypatch):
    keywords_path = tmp_path / "keywords.json"
    write_json(keywords_path, {"AI": ["agent"]})
    client = reference_client(monkeypatch, keywords_path)

    response = client.get("/reference")
    sidebar = sidebar_markup(response.text)

    assert response.status_code == 200
    assert '<div class="app-shell">' in response.text
    assert '<aside class="sidebar" aria-label="Main navigation">' in response.text
    assert 'href="/"' in sidebar
    assert "Dashboard" in sidebar
    assert 'href="/newsletter"' in sidebar
    assert "Weekly Brief" in sidebar
    assert 'href="/reference"' in sidebar
    assert "Reference" in sidebar
    assert 'aria-current="page"' in sidebar
    assert 'href="/intake"' not in sidebar
    assert "Add Article" not in sidebar
    assert 'href="/review"' not in sidebar
    assert "Review Queue" not in sidebar


def test_reference_page_displays_keywords_grouped_by_topic(
    tmp_path,
    monkeypatch,
):
    keywords_path = tmp_path / "keywords.json"
    write_json(
        keywords_path,
        {
            "AI": ["agent", "model"],
            "FinOps": ["unit economics"],
        },
    )
    client = reference_client(monkeypatch, keywords_path)

    response = client.get("/reference")

    assert response.status_code == 200
    assert "Keywords" in response.text
    assert "<h3>AI</h3>" in response.text
    assert "<h3>FinOps</h3>" in response.text
    assert '<span class="chip">agent</span>' in response.text
    assert '<span class="chip">unit economics</span>' in response.text


def test_reference_page_displays_configured_source_links(
    tmp_path,
    monkeypatch,
):
    keywords_path = tmp_path / "keywords.json"
    write_json(keywords_path, {"AI": ["agent"]})
    client = reference_client(
        monkeypatch,
        keywords_path,
        rss_sources={
            "AI": [
                {
                    "name": "Configured RSS",
                    "url": "https://example.com/feed.xml",
                    "type": "rss",
                }
            ]
        },
        sources=[
            {
                "name": "Configured Web",
                "url": "https://example.com/news",
            }
        ],
    )

    response = client.get("/reference")

    assert response.status_code == 200
    assert "Source Links" in response.text
    assert "Configured sources from config.py" in response.text
    assert "Runtime source_index.json is not used here." in response.text
    assert "Configured RSS" in response.text
    assert "AI" in response.text
    assert "rss" in response.text
    assert (
        '<a href="https://example.com/feed.xml" '
        'target="_blank" rel="noopener noreferrer">'
        "https://example.com/feed.xml</a>"
    ) in response.text
    assert "Configured Web" in response.text
    assert "General" in response.text
    assert "web" in response.text
    assert (
        '<a href="https://example.com/news" '
        'target="_blank" rel="noopener noreferrer">'
        "https://example.com/news</a>"
    ) in response.text


def test_reference_page_handles_missing_keyword_and_source_data(
    tmp_path,
    monkeypatch,
):
    keywords_path = tmp_path / "missing_keywords.json"
    client = reference_client(
        monkeypatch,
        keywords_path,
        rss_sources={"AI": [{}]},
        sources=[{}],
    )

    response = client.get("/reference")

    assert response.status_code == 200
    assert "No keywords available" in response.text
    assert "Source Links" in response.text
    assert "&mdash;" in response.text


def test_reference_page_is_read_only(tmp_path, monkeypatch):
    keywords_path = tmp_path / "keywords.json"
    write_json(keywords_path, {"AI": ["agent"]})
    client = reference_client(monkeypatch, keywords_path)

    response = client.get("/reference")
    page_text = response.text.casefold()

    assert response.status_code == 200
    assert "<form" not in page_text
    assert "<button" not in page_text
    assert "create" not in page_text
    assert "edit" not in page_text
    assert "delete" not in page_text
    assert "save" not in page_text
    assert "update" not in page_text
