from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ARTICLE_PATH_HINTS = [
    "/blog/",
    "/news/",
    "/resources/",
    "/post/",
    "/article/",
    "/insights/"
]

BLOCKED_PATH_HINTS = [
    "/login",
    "/sign-in",
    "/signin",
    "/signup",
    "/sign-up",
    "/contact",
    "/pricing",
    "/demo",
    "/privacy",
    "/terms",
    "/careers"
]

BLOCKED_FILE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".mp4",
    ".mov",
    ".css",
    ".js"
)

SOCIAL_DOMAINS = [
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "youtube.com"
]

GENERIC_LINK_TITLES = {
    "all resources",
    "application development",
    "api management",
    "ai & machine learning",
    "events and webinars",
    "free assessment",
    "learn more",
    "read more",
    "resources",
    "blog",
    "news",
    "contact us"
}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_href = ""
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return

        attrs_by_name = dict(attrs)
        href = attrs_by_name.get("href", "")

        if href:
            self.current_href = href
            self.current_text = []

    def handle_data(self, data):
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag):
        if tag != "a" or not self.current_href:
            return

        text = " ".join("".join(self.current_text).split())
        self.links.append({
            "href": self.current_href,
            "text": text
        })
        self.current_href = ""
        self.current_text = []


def fetch_html(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; MarketIntelligenceAgent/1.0)"
        }
    )

    with urlopen(request, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        charset = response.headers.get_content_charset() or "utf-8"

        if "html" not in content_type and "text" not in content_type:
            return ""

        return response.read().decode(charset, errors="replace")


def clean_url(url):
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl()


def is_blocked_url(url):
    parsed = urlparse(url)
    url_lower = url.lower()
    path_lower = parsed.path.lower()

    if not parsed.scheme.startswith("http"):
        return True

    if any(domain in parsed.netloc.lower() for domain in SOCIAL_DOMAINS):
        return True

    if any(path_hint in path_lower for path_hint in BLOCKED_PATH_HINTS):
        return True

    if path_lower.endswith(BLOCKED_FILE_EXTENSIONS):
        return True

    if url_lower.startswith(("javascript:", "mailto:", "tel:")):
        return True

    return False


def looks_like_article_url(url):
    path_lower = urlparse(url).path.lower()
    return any(path_hint in path_lower for path_hint in ARTICLE_PATH_HINTS)


def looks_like_category_page(url):
    path_parts = [
        part for part in urlparse(url).path.lower().strip("/").split("/")
        if part
    ]

    if len(path_parts) == 3 and path_parts[0] == "blog":
        if path_parts[1] in ["topics", "products", "solutions"]:
            return True

    return False


def looks_like_article_title(title):
    title_lower = title.lower().strip()
    words = [word for word in title.replace("&", " ").split() if word]

    if title_lower in GENERIC_LINK_TITLES:
        return False

    return len(words) >= 4


def fetch_listing_links(source, topic):
    try:
        max_links = int(source.get("max_links", 5))
    except (TypeError, ValueError):
        max_links = 5

    html = fetch_html(source["url"])

    if not html:
        return []

    parser = LinkParser()
    parser.feed(html)

    articles = []
    seen_urls = set()

    for link in parser.links:
        href = link["href"].strip()
        title = link["text"].strip()

        if not href or href == "#":
            continue

        if href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue

        if len(title) < 10:
            continue

        if not looks_like_article_title(title):
            continue

        absolute_url = clean_url(urljoin(source["url"], href))

        if absolute_url in seen_urls:
            continue

        if is_blocked_url(absolute_url):
            continue

        if not looks_like_article_url(absolute_url):
            continue

        if looks_like_category_page(absolute_url):
            continue

        articles.append({
            "title": title,
            "url": absolute_url,
            "source": source["name"],
            "source_category": source.get("category", ""),
            "source_type": "web",
            "web_mode": "listing",
            "published_date": "",
            "topic": topic,
            "matched_keywords": []
        })
        seen_urls.add(absolute_url)

        if len(articles) >= max_links:
            break

    return articles
