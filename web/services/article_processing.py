from dataclasses import dataclass
from datetime import datetime

from main import (
    calculate_article_score,
    extract_content,
    get_llm_provider,
    get_recommendation,
)


CONTENT_MIN_LENGTH = 80


@dataclass
class ProcessingResult:
    article_id: str
    success: bool
    article: dict = None
    failure_reason: str = None
    failure_message: str = None
    not_found: bool = False


class ArticleProcessingService:
    def __init__(
        self,
        repository,
        extractor=None,
        llm_provider=None,
        now_fn=None,
        content_min_length=CONTENT_MIN_LENGTH,
    ):
        self.repository = repository
        self.extractor = extractor or extract_content
        self.llm_provider = llm_provider
        self.now_fn = now_fn or self._now
        self.content_min_length = content_min_length

    def process_article(self, article_id):
        article = self.repository.get_article(article_id)
        if article is None:
            return ProcessingResult(
                article_id=article_id,
                success=False,
                not_found=True,
                failure_reason="not_found",
                failure_message="Article not found.",
            )

        if not article.get("url"):
            return self._mark_failed(
                article,
                "missing_url",
                "Article has no URL to process.",
            )

        try:
            extracted_article = self._extract(article)
            content = str(extracted_article.get("content") or "").strip()

            if not content:
                return self._mark_failed(
                    article,
                    "extraction_failed",
                    "Could not extract article content.",
                )

            canonical_url = (
                extracted_article.get("canonical_url")
                or article.get("canonical_url")
            )
            if canonical_url:
                duplicate_article = self.repository.find_by_canonical_url(
                    canonical_url,
                )
                if (
                    duplicate_article is not None
                    and not self._same_article(article, duplicate_article)
                ):
                    return self._mark_failed(
                        article,
                        "duplicate_after_extraction",
                        "Another article with this canonical URL already exists.",
                        {
                            "canonical_url": canonical_url,
                            "duplicate_of_article_id": duplicate_article.get("id"),
                        },
                    )

            if not self._has_acceptable_content(content):
                return self._mark_failed(
                    article,
                    "content_quality_failed",
                    "Extracted content is too short or not article-like.",
                )

            provider = self._get_provider()
            article_for_llm = {
                **article,
                **extracted_article,
                "content": content,
                "content_length": len(content),
            }
            summary_result = self._summarize(provider, article_for_llm)
            summary = str(summary_result.get("summary") or "").strip()
            if not summary:
                return self._mark_failed(
                    article,
                    "llm_summary_failed",
                    "LLM summary was empty or invalid.",
                )

            ranking_result = self._rank(provider, article_for_llm, summary_result)
            score = self._ranking_score(ranking_result)
            recommendation = self.map_recommendation(
                ranking_result.get("recommendation")
                or get_recommendation(score)
            )

            return self._mark_ready(
                article,
                extracted_article,
                summary_result,
                ranking_result,
                score,
                recommendation,
            )
        except Exception as error:
            return self._mark_failed(
                article,
                self._classify_exception(error),
                str(error) or "Unexpected processing error.",
            )

    @staticmethod
    def map_recommendation(recommendation):
        if recommendation in {"Core", "Useful"}:
            return recommendation

        return "Exclude"

    def _extract(self, article):
        try:
            extracted_article = self.extractor(article)
        except Exception as error:
            reason = self._classify_exception(error)
            if reason in {"fetch_failed", "http_error"}:
                raise ProcessingFailure(reason, str(error)) from error
            raise ProcessingFailure("extraction_failed", str(error)) from error

        if not isinstance(extracted_article, dict):
            raise ProcessingFailure(
                "extraction_failed",
                "Extractor returned an invalid result.",
            )

        if extracted_article.get("extraction_status") == "failed":
            raise ProcessingFailure(
                "extraction_failed",
                "Could not extract article content.",
            )

        return extracted_article

    def _get_provider(self):
        return self.llm_provider or get_llm_provider()

    def _summarize(self, provider, article):
        try:
            summary_result = provider.summarize_article(article)
        except Exception as error:
            raise ProcessingFailure("llm_summary_failed", str(error)) from error

        if not isinstance(summary_result, dict):
            raise ProcessingFailure(
                "llm_summary_failed",
                "LLM summary returned an invalid result.",
            )

        if summary_result.get("error"):
            raise ProcessingFailure(
                "llm_summary_failed",
                str(summary_result.get("error")),
            )

        return summary_result

    def _rank(self, provider, article, summary_result):
        article_for_ranking = {
            **article,
            "ai_summary": summary_result,
        }
        try:
            ranking_result = provider.rank_article(article_for_ranking)
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
                "recommendation": "Exclude",
            }

        if not isinstance(ranking_result, dict):
            return {}

        return ranking_result

    def _ranking_score(self, ranking_result):
        if ranking_result.get("score") is not None:
            return ranking_result.get("score")

        if ranking_result.get("ranking_score") is not None:
            return ranking_result.get("ranking_score")

        return calculate_article_score(ranking_result)

    def _has_acceptable_content(self, content):
        if len(content) < self.content_min_length:
            return False

        lower_content = content.casefold()
        empty_markers = [
            "please log in",
            "sign in to continue",
            "subscribe to continue",
            "enable javascript",
            "access denied",
        ]
        return not any(marker in lower_content for marker in empty_markers)

    def _mark_ready(
        self,
        article,
        extracted_article,
        summary_result,
        ranking_result,
        score,
        recommendation,
    ):
        updates = {
            "summary_status": "ready",
            "extraction_status": "success",
            "summary": summary_result.get("summary"),
            "analysis": summary_result.get("analysis"),
            "key_points": summary_result.get("key_points", []),
            "why_it_matters": summary_result.get("why_it_matters", ""),
            "recommendation": recommendation,
            "ranking_score": score,
            "score": score,
            "ranking": ranking_result,
            "use_case": ranking_result.get("use_case", ""),
            "problem_solved": ranking_result.get("problem_solved", ""),
            "reason": ranking_result.get("reason", ""),
            "content": extracted_article.get("content"),
            "content_length": len(extracted_article.get("content") or ""),
            "canonical_url": extracted_article.get(
                "canonical_url",
                article.get("canonical_url"),
            ),
            "failure_reason": None,
            "failure_message": None,
            "duplicate_of_article_id": None,
            "last_processed_at": self.now_fn(),
        }
        return self._update_article(article, updates, success=True)

    def _mark_failed(self, article, reason, message, extra_updates=None):
        failure_reason = getattr(reason, "reason", reason)
        failure_message = getattr(reason, "message", message)
        updates = {
            "summary_status": "failed",
            "summary": None,
            "analysis": None,
            "failure_reason": failure_reason,
            "failure_message": failure_message,
            "last_processed_at": self.now_fn(),
        }
        if extra_updates:
            updates.update(extra_updates)

        return self._update_article(
            article,
            updates,
            success=False,
            failure_reason=failure_reason,
            failure_message=failure_message,
        )

    def _update_article(
        self,
        article,
        updates,
        success,
        failure_reason=None,
        failure_message=None,
    ):
        try:
            updated_article = self.repository.update_article(
                article.get("id") or article.get("canonical_url") or article.get("url"),
                updates,
            )
        except Exception as error:
            return ProcessingResult(
                article_id=article.get("id") or "",
                success=False,
                article=article,
                failure_reason="repository_write_failed",
                failure_message=str(error),
            )

        if updated_article is None:
            return ProcessingResult(
                article_id=article.get("id") or "",
                success=False,
                article=article,
                failure_reason="repository_write_failed",
                failure_message="Article update failed.",
            )

        return ProcessingResult(
            article_id=updated_article.get("id") or article.get("id") or "",
            success=success,
            article=updated_article,
            failure_reason=failure_reason,
            failure_message=failure_message,
        )

    def _classify_exception(self, error):
        if isinstance(error, ProcessingFailure):
            return error.reason

        error_text = str(error).casefold()
        if any(
            marker in error_text
            for marker in ["404", "403", "500", "http error", "status code"]
        ):
            return "http_error"

        if any(
            marker in error_text
            for marker in ["timeout", "dns", "connection", "network"]
        ):
            return "fetch_failed"

        return "unknown_error"

    def _same_article(self, article, other_article):
        article_candidates = self._article_identifiers(article)
        other_candidates = self._article_identifiers(other_article)
        return bool(article_candidates.intersection(other_candidates))

    @staticmethod
    def _article_identifiers(article):
        return {
            str(value)
            for value in [
                article.get("id"),
                article.get("canonical_url"),
                article.get("normalized_url"),
                article.get("url"),
            ]
            if value
        }

    @staticmethod
    def _now():
        return datetime.now().replace(microsecond=0).isoformat()


class ProcessingFailure(Exception):
    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason
        self.message = message
