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

RSS_SOURCES_BY_TOPIC = {
    "AI": [
        {
            "name": "OpenAI News RSS",
            "url": "https://openai.com/news/rss.xml",
            "category": "official_ai"
        },
        {
            "name": "Anthropic News RSS",
            "url": "https://www.anthropic.com/news/rss.xml",
            "category": "official_ai"
        },
        {
            "name": "Google Cloud Blog RSS",
            "url": "https://cloud.google.com/feeds/blog.xml",
            "category": "cloud_provider"
        },
        {
            "name": "AWS Blog RSS",
            "url": "https://aws.amazon.com/blogs/aws/feed/",
            "category": "cloud_provider"
        },
        {
            "name": "Microsoft Azure Blog RSS",
            "url": "https://azure.microsoft.com/en-us/blog/feed/",
            "category": "cloud_provider"
        }
    ],
    "FinOps": [
        {
            "name": "FinOps Foundation Blog",
            "url": "https://www.finops.org/feed/",
            "category": "industry_foundation"
        },
        {
            "name": "Vantage Blog",
            "url": "https://www.vantage.sh/blog/rss.xml",
            "category": "finops_product"
        },
        {
            "name": "IBM Cloudability / Apptio",
            "url": "https://www.ibm.com/blog/category/cloudability/",
            "category": "finops_product"
        },
        {
            "name": "AWS Cloud Financial Management Blog",
            "url": "https://aws.amazon.com/blogs/aws-cloud-financial-management/feed/",
            "category": "cloud_cost"
        },
        {
            "name": "Google Cloud Cost Management",
            "url": "https://cloud.google.com/blog/topics/cost-management",
            "category": "cloud_cost"
        }
    ],
    "ProductObservation": [
        {
            "name": "Vantage Blog",
            "url": "https://www.vantage.sh/blog/rss.xml",
            "category": "competitor_product"
        },
        {
            "name": "CloudZero Blog",
            "url": "https://www.cloudzero.com/blog/",
            "category": "competitor_product"
        },
        {
            "name": "IBM Cloudability / Apptio",
            "url": "https://www.ibm.com/blog/category/cloudability/",
            "category": "competitor_product"
        },
        {
            "name": "eCloudvalley Atlas",
            "url": "https://www.ecloudvalley.com/",
            "category": "product_observation"
        }
    ]
}

LLM_PROVIDER = "gemini"
LLM_MODEL = "gemini-flash-latest"
LLM_FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.0-flash"
]
REPORT_TEMPLATE = "standard_market_analysis"
