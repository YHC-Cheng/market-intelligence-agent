import json
import os

from google import genai

from config import LLM_MODEL
from llm.base import BaseLLMProvider


MAX_CONTENT_LENGTH = 6000


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self.setup_error = ""

        if not api_key:
            self.setup_error = "GEMINI_API_KEY is not set."
            return

        self.client = genai.Client(api_key=api_key)

    def summarize_article(self, article: dict) -> dict:
        if self.setup_error:
            return {
                "summary": "",
                "key_points": [],
                "why_it_matters": "",
                "error": self.setup_error
            }

        prompt = self.create_prompt(article)

        try:
            response = self.client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config={"response_mime_type": "application/json"}
            )
            return self.parse_response(response.text)
        except Exception as error:
            return {
                "summary": "",
                "key_points": [],
                "why_it_matters": "",
                "error": str(error)
            }

    def create_prompt(self, article: dict) -> str:
        matched_keywords = ", ".join(article.get("matched_keywords", []))
        content = article.get("content", "")[:MAX_CONTENT_LENGTH]

        return f"""
You are a market intelligence analyst.

Summarize this article for a business audience.

Return only valid JSON with this shape:
{{
  "summary": "...",
  "key_points": ["...", "...", "..."],
  "why_it_matters": "..."
}}

Article title: {article.get("title", "")}
Source: {article.get("source", "")}
Published date: {article.get("published_date", "")}
Matched keywords: {matched_keywords}

Article content:
{content}
"""

    def parse_response(self, response_text: str) -> dict:
        try:
            data = json.loads(response_text)
            key_points = data.get("key_points", [])

            if not isinstance(key_points, list):
                key_points = []

            return {
                "summary": data.get("summary", ""),
                "key_points": key_points,
                "why_it_matters": data.get("why_it_matters", "")
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "summary": response_text or "",
                "key_points": [],
                "why_it_matters": ""
            }
