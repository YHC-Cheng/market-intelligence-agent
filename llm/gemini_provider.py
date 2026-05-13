import json
import os
import time

from google import genai

from config import LLM_FALLBACK_MODELS, LLM_MODEL
from llm.base import BaseLLMProvider


MAX_CONTENT_LENGTH = 6000
RETRY_DELAYS = [3, 6, 12]


def is_retryable_error(error):
    error_text = str(error).lower()
    retryable_keywords = [
        "503",
        "429",
        "unavailable",
        "rate limit",
        "resource_exhausted",
        "temporary",
        "temporarily",
        "high demand",
        "timeout",
        "deadline"
    ]

    for keyword in retryable_keywords:
        if keyword in error_text:
            return True

    return False


class GeminiProvider(BaseLLMProvider):
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        self.client = None
        self.setup_error = ""
        self.last_model_used = LLM_MODEL

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
            response_text = self.generate_content_text(
                prompt,
                article.get("title", "")
            )
            return self.parse_response(response_text)
        except Exception as error:
            return {
                "summary": "",
                "key_points": [],
                "why_it_matters": "",
                "error": str(error)
            }

    def generate_content_text(self, prompt, article_title):
        model_names = [LLM_MODEL] + LLM_FALLBACK_MODELS
        last_error = None

        for model_index, model_name in enumerate(model_names):
            if model_index > 0:
                print(f"Falling back to model: {model_name}")

            for attempt in range(len(RETRY_DELAYS) + 1):
                try:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config={"response_mime_type": "application/json"}
                    )
                    self.last_model_used = model_name
                    return response.text
                except Exception as error:
                    last_error = error

                    if attempt == len(RETRY_DELAYS) or not is_retryable_error(error):
                        break

                    retry_number = attempt + 1

                    print(
                        f"Retrying Gemini request for article: {article_title} "
                        f"(attempt {retry_number}/{len(RETRY_DELAYS)})"
                    )
                    time.sleep(RETRY_DELAYS[retry_number - 1])

        raise last_error

    def rank_article(self, article: dict) -> dict:
        if self.setup_error:
            return {
                "relevance": 1,
                "use_case_clarity": 1,
                "problem_solution_fit": 1,
                "actionability": 1,
                "credibility_novelty": 1,
                "use_case": "",
                "problem_solved": "",
                "reason": self.setup_error,
                "error": self.setup_error
            }

        prompt = self.create_ranking_prompt(article)

        try:
            response_text = self.generate_content_text(
                prompt,
                article.get("title", "")
            )
            return self.parse_ranking_response(response_text)
        except Exception as error:
            return {
                "relevance": 1,
                "use_case_clarity": 1,
                "problem_solution_fit": 1,
                "actionability": 1,
                "credibility_novelty": 1,
                "use_case": "",
                "problem_solved": "",
                "reason": str(error),
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

    def create_ranking_prompt(self, article: dict) -> str:
        matched_keywords = ", ".join(article.get("matched_keywords", []))
        content = article.get("content", "")[:MAX_CONTENT_LENGTH]

        return f"""
You are a market intelligence analyst.

Evaluate this article for market research value.
Pay special attention to whether the article has a clear use case and whether it clearly explains what problem is being solved.

Score each dimension from 1 to 5:
1. relevance: How closely the article matches the current topic.
2. use_case_clarity: Whether it explains who uses it, in what situation, and what the workflow looks like.
3. problem_solution_fit: Whether it clearly states the problem and how the product or feature solves it.
4. actionability: Whether it can become product insight, market analysis, competitor analysis, slide material, or a follow-up research question.
5. credibility_novelty: Whether the source is credible and the article is recent, a new feature, GA, preview, partnership, or important market signal.

Be strict:
- Give 5 for use_case_clarity only when the article describes a concrete user, workflow, and usage scenario.
- Give 5 for problem_solution_fit only when the pain point and the solution are both explicit and connected.
- General news roundups can be credible and relevant, but should not receive perfect use_case_clarity or problem_solution_fit unless they contain a specific, clearly explained use case.
- Prefer 3 or 4 when the article is useful but the use case or problem-solution story is spread across many announcements.

Return only valid JSON with this shape:
{{
  "relevance": 1,
  "use_case_clarity": 1,
  "problem_solution_fit": 1,
  "actionability": 1,
  "credibility_novelty": 1,
  "use_case": "...",
  "problem_solved": "...",
  "reason": "..."
}}

Topic: {article.get("topic", "")}
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

    def parse_ranking_response(self, response_text: str) -> dict:
        try:
            data = json.loads(response_text)

            return {
                "relevance": data.get("relevance", 1),
                "use_case_clarity": data.get("use_case_clarity", 1),
                "problem_solution_fit": data.get("problem_solution_fit", 1),
                "actionability": data.get("actionability", 1),
                "credibility_novelty": data.get("credibility_novelty", 1),
                "use_case": data.get("use_case", ""),
                "problem_solved": data.get("problem_solved", ""),
                "reason": data.get("reason", "")
            }
        except (json.JSONDecodeError, TypeError):
            return {
                "relevance": 1,
                "use_case_clarity": 1,
                "problem_solution_fit": 1,
                "actionability": 1,
                "credibility_novelty": 1,
                "use_case": "",
                "problem_solved": "",
                "reason": response_text or "",
                "error": "Gemini did not return valid JSON."
            }
