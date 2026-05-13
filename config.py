DEFAULT_TOPIC = "AI"

SOURCES = [
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/news/"
    },
    {
        "name": "Anthropic News",
        "url": "https://www.anthropic.com/news"
    },
    {
        "name": "Google Cloud Blog",
        "url": "https://cloud.google.com/blog"
    },
    {
        "name": "AWS Blog",
        "url": "https://aws.amazon.com/blogs/"
    },
    {
        "name": "Microsoft Azure Blog",
        "url": "https://azure.microsoft.com/en-us/blog/"
    },
    {
        "name": "FinOps Foundation",
        "url": "https://www.finops.org/blog/"
    },
    {
        "name": "Vantage Blog",
        "url": "https://www.vantage.sh/blog"
    }
]

OUTPUT_FORMATS = [
    "market_brief.md",
    "market_analysis_report.md",
    "slide_draft.md",
    "sources.json"
]

RSS_SOURCES = [
    {
        "name": "OpenAI News RSS",
        "url": "https://openai.com/news/rss.xml"
    },
    {
        "name": "AWS Blog RSS",
        "url": "https://aws.amazon.com/blogs/aws/feed/"
    }
]

LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini-flash-latest"
LLM_FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash"
]
REPORT_TEMPLATE = "standard_market_analysis"
