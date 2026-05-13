import json
import os
import time

from google import genai

from config import (
    LLM_FALLBACK_MODELS,
    LLM_MODEL,
    MAX_LLM_RETRIES,
    STOP_ON_RATE_LIMIT
)
from llm.base import BaseLLMProvider


MAX_CONTENT_LENGTH = 6000
RETRY_DELAYS = [3, 6, 12]


def is_rate_limit_error(error):
    error_text = str(error).lower()
    rate_limit_keywords = [
        "429",
        "resource_exhausted",
        "quota",
        "rate limit"
    ]

    for keyword in rate_limit_keywords:
        if keyword in error_text:
            return True

    return False


def is_retryable_error(error):
    error_text = str(error).lower()
    retryable_keywords = [
        "503",
        "unavailable",
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

    def generate_content_text(
        self,
        prompt,
        article_title,
        response_mime_type="application/json"
    ):
        model_names = [LLM_MODEL] + LLM_FALLBACK_MODELS
        last_error = None

        for model_index, model_name in enumerate(model_names):
            if model_index > 0:
                print(f"Falling back to model: {model_name}")

            for attempt in range(MAX_LLM_RETRIES + 1):
                try:
                    request = {
                        "model": model_name,
                        "contents": prompt
                    }

                    if response_mime_type:
                        request["config"] = {
                            "response_mime_type": response_mime_type
                        }

                    response = self.client.models.generate_content(
                        **request
                    )
                    self.last_model_used = model_name
                    return response.text
                except Exception as error:
                    last_error = error

                    if is_rate_limit_error(error) and STOP_ON_RATE_LIMIT:
                        print(
                            "Rate limit reached. Skipping further retries for: "
                            f"{article_title}"
                        )
                        raise error

                    if attempt == MAX_LLM_RETRIES or not is_retryable_error(error):
                        break

                    retry_number = attempt + 1
                    retry_delay = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]

                    print(
                        f"Retrying Gemini request for article: {article_title} "
                        f"(attempt {retry_number}/{MAX_LLM_RETRIES})"
                    )
                    time.sleep(retry_delay)

        raise last_error

    def generate_market_analysis_report(
        self,
        topic: str,
        market_brief: str,
        ranked_sources: str,
        references_text: str
    ) -> str:
        if self.setup_error:
            raise RuntimeError(self.setup_error)

        prompt = self.create_market_analysis_prompt(
            topic,
            market_brief,
            ranked_sources,
            references_text
        )

        return self.generate_content_text(
            prompt,
            "market analysis report",
            response_mime_type=None
        )

    def generate_slide_draft(
        self,
        topic: str,
        market_analysis_report: str
    ) -> str:
        if self.setup_error:
            raise RuntimeError(self.setup_error)

        prompt = self.create_slide_draft_prompt(
            topic,
            market_analysis_report
        )

        return self.generate_content_text(
            prompt,
            "slide draft",
            response_mime_type=None
        )

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

    def create_market_analysis_prompt(
        self,
        topic: str,
        market_brief: str,
        ranked_sources: str,
        references_text: str
    ) -> str:
        return f"""
You are a senior product manager and market intelligence analyst.

Write a Traditional Chinese market analysis report.

Important rules:
- Do not summarize articles one by one.
- Synthesize the sources into market-level product insights.
- Prioritize articles whose recommendation is Core or Useful.
- Use Background articles only as supporting context.
- Do not use Exclude articles.
- Emphasize sources with clear use cases or strong problem-solution fit.
- Do not invent facts that are not supported by the provided sources.
- If the evidence is insufficient, explicitly write: 「目前資料不足以判斷」.
- Make the product implications concrete for SaaS, FinOps, or Cloud Management products.
- When a claim is based on a source, cite it inline using [來源 1], [來源 2], etc.
- The inline citation numbers must match the reference list exactly.
- Include section 5 and copy the provided references exactly under that section.

Use exactly this structure:

# Market Analysis Report: {topic}

## 1. 市場趨勢 / 新趨勢

整理本週觀察到的主要市場變化。

請回答：
- 這週出現了什麼值得注意的新趨勢？
- 哪些產品、技術、廠商動作或 use case 值得關注？
- 這些訊號是否代表市場方向正在改變？

## 2. 市場問題或痛點

整理這些趨勢背後反映的問題。

請回答：
- 企業、使用者或產品團隊正在遇到什麼問題？
- 現有流程或工具為什麼不足？
- 為什麼這個問題現在變得重要？

如果資料不足以判斷，請明確寫：
「目前資料不足以完整判斷市場痛點，但可觀察到……」

## 3. 現有工具或解法

整理文章中提到的產品、工具、平台、技術或做法。

請回答：
- 目前市場上出現了哪些解法？
- 它們分別解決什麼問題？
- 是否有明確 use case 或實際應用場景？

## 4. 給產品的啟示

從產品經理角度整理可以借鏡的方向。

請回答：
- 這對 SaaS / FinOps / Cloud Management 產品有什麼啟發？
- 是否可以轉化成產品功能、使用者體驗、權限治理、自動化流程或產品定位？
- 後續值得追蹤或驗證什麼？

## 5. 參考資料

Copy the provided references exactly. Do not include Exclude sources.

Market brief:
{market_brief}

Ranked sources:
{ranked_sources}

References:
{references_text}
"""

    def create_slide_draft_prompt(
        self,
        topic: str,
        market_analysis_report: str
    ) -> str:
        return f"""
You are a senior product manager creating an editable Markdown slide draft for a market sharing session.

Write in Traditional Chinese.
Use only the information in the market analysis report.
Do not summarize articles one by one.
Make the deck feel like a product manager's market narrative, not an information dump.
Use clear, intuitive business language. Avoid abstract analyst jargon.
Do not make the deck look like a single-vendor briefing.
Even if most evidence comes from AWS or another single vendor, elevate it into market trends or product implications.
Keep each slide focused on one clear message.
Each slide can have at most 4 bullets.
Each bullet should express one point in one concise line.
Each core message should be 35 Chinese characters or fewer when possible.
Each bullet should be 35 Chinese characters or fewer when possible.
If one bullet becomes too long, split it into two bullets.
Preserve [來源 1], [來源 2], etc. citation markers when making claims.
Do not invent facts that are not in the report.
If evidence is insufficient, explicitly write: 「目前資料不足以判斷」.

Return exactly this structure:

# Slide Draft: {topic}

## Slide 1：本週市場趨勢 / 新趨勢

### 核心訊息

用 35 字以內的一句話聚焦本週最重要的一個市場變化。不要同時塞入多個趨勢。
請使用清楚、直覺的商業語言。

### 重點內容

- 最多 4 個 bullet。
- 每個 bullet 儘量不超過 35 字。
- 只支撐同一個主要市場變化。
- 優先整理市場方向、廠商動作、技術變化或代表性訊號。
- 不要把這頁寫成單一廠商專題。
- 不要逐篇摘要文章。

### 講稿提示

用 2 到 4 句話說明這頁要如何講成一個清楚的市場故事。

---

## Slide 2：市場問題與現有解法

### 核心訊息

用 35 字以內的一句話說明使用者或產品團隊真正感受到的問題，以及市場正在出現的解法。

### 重點內容

- 最多 4 個 bullet。
- 每個 bullet 儘量不超過 35 字。
- 用產品 / 使用者容易理解的語言描述市場問題，不要過度抽象。
- 說明現有工具、平台、技術或產品如何解決問題。
- 優先引用有明確 use case 或 problem-solution fit 的內容。

### 講稿提示

用 2 到 4 句話說明問題為什麼重要，以及現有解法代表什麼市場訊號。

---

## Slide 3：代表性 Use Case / 工具案例

### 核心訊息

用 35 字以內的一句話說明代表性 use case 顯示的市場變化。
不要只聚焦某一個供應商。

### 重點內容

- 2 到 4 個 bullet。
- 每個 bullet 儘量不超過 35 字。
- 每個 bullet 是一個具體 use case 或工具案例。
- 每個 bullet 都要說清楚：使用情境、解決什麼問題、為什麼值得產品團隊關注。
- 如果某案例來自單一供應商，請提升成可觀察的市場需求。
- 不要列出沒有明確使用情境的案例。

### 講稿提示

用 2 到 4 句話說明這些案例如何連回產品機會或市場驗證方向。

---

## Slide 4：給產品的啟示與後續觀察

### 核心訊息

用 35 字以內的一句話說明這些市場訊號對產品策略的意義。

### 重點內容

- 必須收斂成以下 3 個 bullet，且每個 bullet 只講一個方向：
- Agent Governance：代理權限、稽核、操作邊界。
- Workflow Integration：降低 legacy / existing workflow 整合門檻。
- Cost & Reliability：降低 AI agent 執行成本與延遲，避免規模化後成本失控。

### 講稿提示

用 2 到 4 句話說明這三個方向如何轉化成產品能力、UX、治理、自動化或定位。

---

## References

Extract and preserve the references from the report.
Use this format:

[來源 1] title  
- Source: source
- Category: category
- Recommendation: recommendation
- Published date: published_date
- URL: url

Market analysis report:
{market_analysis_report}
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
