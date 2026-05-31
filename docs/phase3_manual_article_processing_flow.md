# Market Intelligence Agent 2.0 Phase 3 Manual Article Processing Flow

## 1. Purpose

Phase 3 connects the existing FastAPI / Jinja Web UI to the real backend article processing workflow. Manual input only replaces automatic source collection; it does not replace the rest of the pipeline.

The manual article flow must preserve:

- deduplication
- article extraction
- content quality check
- LLM summary / analysis
- ranking
- recommendation
- JSON repository write
- Web UI display
- Weekly Brief selection

Phase 3 does not introduce React, a database, a queue, a frontend build pipeline, production deployment, email sending, or a rewrite of the 1.0 pipeline.

## 2. Current Baseline

Current passing test baseline:

```text
.venv/bin/python -m pytest -q
143 passed, 1 warning
```

Reusable existing components:

- `web/app.py` has Dashboard, intake, article detail, retry/delete, Needs Attention, and newsletter routes.
- `JsonKnowledgeRepository` can read/write JSON, create/delete manual articles, update article fields, and perform duplicate checks.
- `main.py` already contains extraction, LLM summary, ranking, recommendation, and knowledge upsert logic.
- `article_detail.html` exposes Generate Summary, Retry Generate Summary, Delete, failure details, and duplicate-after-extraction links.

## 3. Summary Status Vocabulary

Phase 3 primary statuses are limited to:

| Backend value | UI display | Meaning |
|---|---|---|
| `to_extract` | To Extract | Workspace article exists but extraction / summary has not run |
| `ready` | Ready | Extraction, quality check, LLM summary, ranking, and repository write succeeded |
| `failed` | Failed | Article entered workspace, but one processing step failed |

Legacy fallback mapping:

- `needs_summary` maps to `to_extract`.
- `analysis_status = not_started` maps to `to_extract`.
- `analysis_status = pending` maps to `to_extract`.
- UI copy uses `To Extract` instead of `To-do`.
- New manual articles should use `summary_status = "to_extract"`.

## 4. Manual Input Flow

Full flow:

```text
Manual input
-> Validate URL
-> Validate topic
-> Normalize URL
-> Pre-deduplicate by normalized_url
-> Create workspace article record
-> Display in Articles list as To Extract
-> User clicks Generate Summary
-> Processing deduplicate guard
-> Fetch / extract article content
-> Canonical URL duplicate check
-> Content quality check
-> LLM summary / analysis
-> Ranking / recommendation
-> Write to JSON knowledge repository
-> Web UI display
-> Weekly Brief selection
```

Invalid manual input should not create article records. Valid and non-duplicate input should create a `to_extract` article. `to_extract` articles must appear in the Articles list.

## 5. URL Validation and Normalization Rules

Implementation should use `urllib.parse`.

Rules:

- Only `http` and `https` are allowed.
- Scheme should be lowercase.
- Host should be lowercase.
- Fragment should be removed.
- Trailing slash should be removed except root path.
- Default ports may be removed.
- Query string should be kept in the Phase 3 initial implementation.
- Tracking query cleanup can be deferred to a later phase.

Acceptance criteria:

- Non-`http`/`https` URLs are rejected.
- Host case does not affect deduplication.
- Fragment does not affect deduplication.
- Trailing slash does not affect deduplication.
- Duplicate normalized URL does not create a new article.

## 6. Deduplication Rules

Phase 3 uses two-stage deduplication.

Stage 1: Pre-deduplication

- Happens during manual input.
- Uses `normalized_url`.
- `duplicate_url` should not create a new article.
- `duplicate_url` should redirect or link to the existing article detail.

Stage 2: Processing deduplication

- Happens after extraction.
- Uses `canonical_url` if available.
- `duplicate_after_extraction` marks the new article as failed.
- If possible, store `duplicate_of_article_id` for linking to the existing article.

## 7. Single Article Processing Service Boundary

Generate Summary should be implemented through:

```text
web/services/article_processing.py
```

Do not put the full processing workflow directly in FastAPI route handlers.

The service should:

- load article
- fetch article
- classify fetch / HTTP errors
- extract content
- check content quality
- check canonical duplicate
- call LLM summary / analysis
- rank article
- map recommendation
- update JSON repository
- return success / failure result

Routes should stay thin:

- `POST /articles/{article_id}/generate-summary` should call the service and redirect back to Article Detail.
- Retry should reuse the same service.

## 8. Failure Reason Rules

Do not write errors into `summary`. `summary` is only for successful AI-generated summaries. Failed articles should use `failure_reason` and `failure_message`.

| failure_reason | Meaning | Creates article record | Initial action |
|---|---|---:|---|
| `missing_url` | Missing URL | No | Form validation |
| `invalid_url` | Invalid or unsupported URL | No | Form validation |
| `missing_topic` | Missing topic | No | Form validation |
| `unsupported_topic` | Topic is not allowed | No | Form validation |
| `duplicate_url` | `normalized_url` already exists during manual input | No | Open existing article |
| `duplicate_after_extraction` | `canonical_url` matches another article after extraction | Yes | Delete |
| `fetch_failed` | Timeout, DNS, or connection error | Yes | Retry / Delete |
| `http_error` | Source returned HTTP error | Yes | Retry / Delete |
| `extraction_failed` | HTML fetched but article content extraction failed | Yes | Retry / Delete |
| `content_quality_failed` | Content too short, non-article page, paywall, login page, etc. | Yes | Delete |
| `llm_summary_failed` | LLM call failed, returned invalid format, or empty summary | Yes | Retry / Delete |
| `repository_write_failed` | Processing succeeded but JSON write failed | Yes, if failure state can be persisted | Retry / Delete |
| `unknown_error` | Unclassified error | Yes | Retry / Delete |

The current extraction code may not yet classify all failures precisely, so later implementation should split processing into explicit steps:

```text
fetch -> HTTP status check -> extraction -> content quality check -> LLM summary -> repository write
```

## 9. Retry and Delete Rules

Retryable failure reasons:

- `fetch_failed`
- `http_error`
- `extraction_failed`
- `llm_summary_failed`
- `repository_write_failed`
- `unknown_error`

Not retryable failure reasons:

- `duplicate_after_extraction`
- `content_quality_failed`
- `missing_url`
- `invalid_url`
- `missing_topic`
- `unsupported_topic`
- `duplicate_url`

UI behavior:

- `to_extract`: show Generate Summary.
- `failed` + retryable: show Retry Generate Summary and Delete.
- `failed` + not retryable: show Delete.
- `duplicate_after_extraction`: show Delete and existing article link if `duplicate_of_article_id` exists.
- `ready`: Generate Again can be deferred.

Delete can be hard delete in the Phase 3 initial implementation.

## 10. Recommendation Mapping Rules

Phase 3 UI supports only:

- Core
- Useful
- Exclude

The legacy pipeline may return `Background`.

Rules:

- New manual summary flow should not produce `Background`.
- If the legacy pipeline returns `Background`, map it to `Exclude` in the manual flow.
- Legacy `Background` articles may remain compatible but must not enter Weekly Brief.

| Pipeline recommendation | Phase 3 recommendation |
|---|---|
| Core | Core |
| Useful | Useful |
| Background | Exclude |
| empty / unknown | Exclude |

## 11. Weekly Brief Selection Logic

Include only:

- `summary_status == ready`
- `recommendation in {"Core", "Useful"}`
- non-empty summary

Exclude:

- `summary_status == failed`
- `summary_status == to_extract`
- `recommendation == Exclude`
- `recommendation == Background`
- missing summary

Do not fallback to all articles.

If not enough articles exist, show a warning or empty state. Do not error and do not automatically include failed, `to_extract`, or `Exclude` articles.

Sorting:

1. Core before Useful
2. `last_processed_at` desc
3. `ranking_score` desc if available

Limits:

- Total max articles: 10
- Each topic max articles: 3

Phase 3 does not create Weekly Brief snapshots. `newsletter/current` should use the current repository state.

## 12. Needs Attention Filter

Needs Attention is a derived UI filter only. It is not persisted and does not add a new `summary_status`.

An article needs attention if any of these are true:

- `summary_status == failed`
- `summary_status == to_extract`
- recommendation is missing or empty
- recommendation is `Background`
- `summary_status == ready` but summary is missing or empty

Healthy ready articles with non-empty summaries and recommendation `Core`, `Useful`, or `Exclude` do not need attention.

## 13. JSON Repository Write Policy

The repository is the only JSON write entry point. Route handlers should not directly manipulate JSON files. The processing service should write through repository methods. Repository write failures should be caught and represented as `repository_write_failed` where possible.

Expected repository methods in later PRs:

- `list_articles()`
- `get_article(article_id)`
- `find_by_normalized_url(normalized_url)`
- `find_by_canonical_url(canonical_url)`
- `create_manual_article(...)`
- `update_article(article_id, updates)`
- `delete_article(article_id)`

Limitation: if the JSON repository is completely unwritable, `repository_write_failed` itself may not be persisted.

## 14. Acceptance Criteria

Status vocabulary:

- Phase 3 primary statuses are `to_extract`, `ready`, and `failed`.
- `needs_summary` is treated as legacy and mapped to `to_extract`.
- `analysis_status` values `not_started` and `pending` can fallback to `to_extract`.
- UI copy uses `To Extract` instead of `To-do`.

Manual input:

- `missing_url`, `invalid_url`, `missing_topic`, and `unsupported_topic` do not create article records.
- `duplicate_url` does not create a new article.
- Valid and non-duplicate input creates a `to_extract` article.
- `to_extract` articles appear in the Articles list.

Generate Summary:

- Success sets `summary_status = ready`.
- Success writes `summary`, `analysis`, `recommendation`, `ranking_score`, and `last_processed_at`.
- Success clears `failure_reason` and `failure_message`.
- Failure sets `summary_status = failed`.
- Failure clears `summary` and `analysis`.
- Failure writes `failure_reason`, `failure_message`, and `last_processed_at`.

Retry / delete:

- Retryable failures show Retry Generate Summary.
- All failed articles can be deleted.
- Retry reuses the single article processing service.

Weekly Brief:

- Only ready + Core / Useful articles are included.
- Failed, `to_extract`, Exclude, Background, and missing summary are excluded.
- No fallback to all articles.
- Insufficient articles show a warning or empty state without error.

Background handling:

- Manual flow maps Background to Exclude.
- Background articles do not enter Weekly Brief.

Needs Attention:

- Needs Attention is derived only and is not stored as a formal status.
- Failed, `to_extract`, missing recommendation, empty recommendation, Background, and ready-without-summary articles are included.
- Healthy ready articles with `Core`, `Useful`, or `Exclude` and a non-empty summary are excluded.

## 15. Known Limitations and Next Phase

Known limitations:

- Delete is hard delete.
- Generate Summary runs synchronously in request/response.
- There is no background queue.
- There are no Weekly Brief snapshots.
- There is no email sending.
- There is no database; the 2.0 workflow remains JSON repository based.
- Manual workflow exists, but production readiness still depends on final acceptance and usage validation.

Suggested next phase:

- Phase 4 should focus on acceptance hardening, operational safety, or production-readiness decisions before adding larger workflow capabilities.
