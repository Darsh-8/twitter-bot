"""Seed list of MVP RSS sources. Loaded by the Alembic data migration / seed script.

Phase 2 will replace/extend this with additional NewsSourceClient adapters
(NewsAPI, GitHub Trending, generic webhooks) registered against new
`sources.source_type` values.
"""

MVP_RSS_SOURCES = [
    {
        "name": "OpenAI Blog",
        "source_type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "category": "lab_official",
        "trust_weight": 1.0,
    },
    {
        "name": "Anthropic Blog",
        "source_type": "rss",
        "url": "https://www.anthropic.com/rss.xml",
        "category": "lab_official",
        "trust_weight": 1.0,
    },
    {
        "name": "Google DeepMind Blog",
        "source_type": "rss",
        "url": "https://deepmind.google/blog/rss.xml",
        "category": "lab_official",
        "trust_weight": 1.0,
    },
    {
        "name": "Meta AI Blog",
        "source_type": "rss",
        "url": "https://ai.meta.com/blog/rss/",
        "category": "lab_official",
        "trust_weight": 1.0,
    },
    {
        "name": "HuggingFace Blog",
        "source_type": "rss",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "lab_official",
        "trust_weight": 0.9,
    },
    {
        "name": "TechCrunch AI",
        "source_type": "rss",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "category": "tech_media",
        "trust_weight": 0.7,
    },
    {
        "name": "The Verge AI",
        "source_type": "rss",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
        "category": "tech_media",
        "trust_weight": 0.7,
    },
    {
        "name": "Ars Technica",
        "source_type": "rss",
        "url": "https://arstechnica.com/tag/ai/feed/",
        "category": "tech_media",
        "trust_weight": 0.7,
    },
    {
        "name": "VentureBeat AI",
        "source_type": "rss",
        "url": "https://venturebeat.com/category/ai/feed/",
        "category": "tech_media",
        "trust_weight": 0.65,
    },
    {
        "name": "arXiv cs.AI",
        "source_type": "rss",
        "url": "https://rss.arxiv.org/rss/cs.AI",
        "category": "research",
        "trust_weight": 0.6,
    },
    {
        "name": "MIT Technology Review",
        "source_type": "rss",
        "url": "https://www.technologyreview.com/feed/",
        "category": "tech_media",
        "trust_weight": 0.75,
    },
    {
        "name": "Hacker News AI",
        "source_type": "rss",
        "url": "https://hnrss.org/newest?q=GPT+OR+Claude+OR+Gemini+OR+Llama+OR+%22AI+agent%22",
        "category": "community",
        "trust_weight": 0.5,
    },
    {
        "name": "Simon Willison's Blog",
        "source_type": "rss",
        "url": "https://simonwillison.net/atom/everything/",
        "category": "tech_media",
        "trust_weight": 0.75,
    },
]
