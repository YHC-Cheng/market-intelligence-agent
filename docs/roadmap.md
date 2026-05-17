# Roadmap

| Phase | Name | Goal | Status |
|---|---|---|---|
| Phase 0 | Project setup | Set up project structure, dependencies, and baseline files | Completed |
| Phase 1 | RSS metadata collection | Collect article titles, URLs, source names, and published dates from RSS feeds | Completed |
| Phase 1.5 | Keyword filtering | Filter collected articles by topic keywords | Completed |
| Phase 2 | Article content extraction | Extract readable article content with `trafilatura` | Completed |
| Phase 3 | Market brief MVP | Generate a basic market brief from extracted articles | Completed |
| Phase 3.5 | Gemini AI summary integration | Use Gemini to generate article summaries, key points, and why-it-matters notes | Completed |
| Phase 4 | Article value ranking | Rank articles by relevance, use case clarity, problem-solution fit, actionability, and novelty | Completed |
| Phase 4.5 | LLM reliability and cost control | Add retry, fallback models, call limits, and safer rate-limit handling | Completed |
| Phase 4.6 | Weekly topic cache | Store summary, ranking, and report cache by topic and ISO week | Completed |
| Phase 5 | Market analysis report generator | Generate a structured product-oriented market analysis report | Completed |
| Phase 5.1 | Source strategy and references | Manage sources by topic/type and add traceable report references | Completed |
| Phase 5.2 | Source validation | Validate configured sources with a standalone script | Completed |
| Phase 5.3 | Source type classification | Classify sources as `rss` or `web`; skip unsupported web sources | Completed |
| Phase 5.4 | LLM call budget and report cache | Limit articles per run and cache market analysis reports | Completed |
| Phase 6 | Slide draft generator | Convert market analysis reports into editable Markdown slide drafts | Completed |
| Phase 7.1 | Static web source parsing | Treat configured static web pages as articles during content extraction | Completed |
| Phase 7.2 | Listing web source parsing | Parse listing pages and collect article links from web sources | Completed |
| Phase 7.3 | Weekly deduplication and freshness control | Track seen URLs, content hashes, and exclude repeated or old articles from weekly reports | Completed |
| Phase 7.4 | Knowledge Base Builder | Persist long-term article knowledge, market insight records, and source index metadata | Completed |
| Phase 8.1 | Automation-ready workflow refactor | Add run id, run summary, latest outputs, report index, and report query support before scheduled automation | Completed |
| Phase 8.2 | GitHub Actions weekly runner | Add PR tests and scheduled/manual weekly market intelligence runner | Completed |
| Phase 8.3 | Gemini quota risk reduction | Reduce default weekly LLM volume to lower Gemini free tier rate-limit risk | Completed |
| Phase 8.4 | LLM reliability improvements | Reduce unnecessary LLM calls, add request pacing, and improve 429 handling | Completed |
| Phase 8.5 | Output quality checks | Improve validation and quality checks for generated outputs | Completed |
| Phase 9 | Notification and review workflow | Add proactive weekly report notification and review records | Planned |
| Phase 10 | Agentic research planning | Let the agent plan research tasks and identify follow-up questions | Planned |

## Phase 7｜Web Source Parsing

Phase 7 extends the workflow to support market intelligence sources that do not provide RSS feeds.

### Phase 7.1｜Static Web Source Parsing

目標：

支援 `type = "web"` 且 `web_mode = "static"` 的來源，把指定頁面當成一篇 article 進入後續流程。

狀態：Completed

適合來源：

- eCloudvalley Atlas
- IBM Cloudability / Apptio product pages
- Google Cloud Cost Management pages
- competitor product pages
- solution pages

### Phase 7.2｜Listing Web Source Parsing

目標：

支援 `type = "web"` 且 `web_mode = "listing"` 的來源，從列表頁抓取文章連結。

狀態：Completed

適合來源：

- CloudZero Blog
- Anthropic News / Blog
- Google Cloud Blog topic pages
- IBM Blog category pages

### Phase 7.3｜Weekly Deduplication & Freshness Control

目標：

使用 `data/history/processed_articles.json` 記錄已看過的 URL、content hash、first seen、last seen 與 seen count，並標記每篇文章的 freshness status。

狀態：Completed

處理規則：

- `new` / `updated` 優先進入 summary、ranking、report
- `unknown` 可以進 ranking，但不能作為本週新趨勢主證據
- `repeated` / `old` 預設排除在本週報告之外

### Phase 7.4｜Knowledge Base Builder

目標：

建立 `data/knowledge/`，長期保存已讀過且有價值的市場資料，方便之後查詢、回顧趨勢與累積產品洞察。

狀態：Completed

新增檔案：

- `data/knowledge/articles_knowledge.json`
- `data/knowledge/market_insights.json`
- `data/knowledge/source_index.json`

資料分工：

- `data/cache/` 用於同週省 API call，保存 summary、ranking 與 report cache。
- `data/history/processed_articles.json` 用於跨週 dedup、content hash 與 freshness control。
- `data/knowledge/` 用於長期保存已讀文章、摘要、ranking、use case、problem solved、recommendation、source index 與 market insights。

## Phase 8｜Automation Readiness

Phase 8 會讓 workflow 可以被排程工具穩定執行。Phase 8.1 先不新增 GitHub Actions，而是先讓程式本身具備可追蹤、可查詢、可回溯的執行紀錄。

### Phase 8.1｜Automation-ready Workflow Refactor

目標：

每次執行 `main.py` 都建立 run metadata，讓人工執行與未來排程執行都能留下清楚紀錄。

狀態：Completed

新增能力：

- 支援 `--run-id`，讓外部排程工具可指定穩定 run id。
- 支援 `--run-mode manual|weekly|test`，讓人工執行與排程執行可區分。
- `run_id` 使用 `YYYY-MM-DD_HHMM_{run_mode}_{topic}` 格式。
- 每次執行寫入 `outputs/runs/{run_id}/run_summary.json`。
- 每次執行將本次產出的 reports、slides 與 output quality review 複製到 `outputs/runs/{run_id}/`。
- 每次成功執行同步更新 `outputs/latest/{topic}/`。
- 更新 `outputs/index/report_index.json`，記錄 run id、topic、run mode、status、quality score 與 report paths。
- 新增 `scripts/query_reports.py`，可查詢 latest、list 與指定 run id。

設計原則：

- 不改變 RSS/web parsing、freshness history、weekly cache、knowledge base 與 LLM provider 架構。
- 成功與失敗執行都應留下 `run_summary.json`。
- 保留既有 `python3 main.py` 與 `python3 main.py --topic FinOps` 用法。

### Phase 8.2｜GitHub Actions Weekly Runner

目標：

新增 GitHub Actions workflow，讓 PR 具備 automated checks，並讓 market intelligence workflow 可以每週排程或手動執行。

狀態：Completed

新增能力：

- `.github/workflows/test.yml` 在 pull request 與 push 到 `main` 時執行 `python -m pytest`。
- `.github/workflows/weekly-market-intelligence.yml` 支援 weekly schedule 與 `workflow_dispatch`。
- 手動執行 weekly workflow 時可選 `AI`、`FinOps` 或 `ProductObservation`。
- 手動執行 weekly workflow 時可設定 `max_articles`，預設為 `1`。
- GitHub Actions weekly runner 預設 `max_articles = 1`，以降低 Gemini free tier rate limit 風險；若手動執行時提高 `max_articles`，可能遇到 Gemini 429 quota error。
- 手動執行 weekly workflow 時可設定 `skip_slides`，預設為 `true`。
- scheduled weekly run 預設略過 slide draft generation，以降低 Gemini API request 數量與 429 quota risk。
- 若手動執行時將 `skip_slides` 設為 `false`，會產生 slide draft，但可能增加 Gemini 429 quota risk。
- workflow 使用 GitHub repository secret `GEMINI_API_KEY`。
- weekly outputs 會以 GitHub Actions artifact `market-intelligence-outputs` 保存 30 天。

注意事項：

- workflow 不會自動 commit `outputs/` 回 repo。
- workflow 不會自動 commit `data/history/` 或 `data/knowledge/` 回 repo。
- 目前未新增 Slack、Email、GitHub Pages 或其他通知/發布流程。

### Phase 8.3｜Gemini Quota Risk Reduction

目標：

降低 GitHub Actions weekly runner 在 Gemini free tier 上遇到 429 quota error 的機率。

狀態：Completed

新增能力：

- workflow_dispatch 的 `max_articles` 預設值從 `3` 調整為 `1`。
- scheduled run 的 fallback `MAX_ARTICLES` 預設值從 `3` 調整為 `1`。
- README 與 roadmap 補充手動提高 `max_articles` 可能增加 Gemini 429 quota error 風險。

### Phase 8.4｜LLM Reliability Improvements

目標：

讓 weekly automation 更有意識地控制 LLM request 數量、request pacing 與 429 quota handling。

狀態：Completed

已完成：

- 新增 weekly runner `skip_slides` option。
- scheduled weekly run 預設略過 slide draft generation。
- manual run 可將 `skip_slides` 設為 `false` 以產生 slide draft。
- 新增 `LLM_REQUEST_DELAY_SECONDS`，可設定 LLM requests 之間的固定 delay。
- Gemini provider 會在一次 LLM request 完成後套用 request delay；預設為 `0`，本地開發不會等待。

### Phase 8.5｜Output Quality Checks

狀態：Completed

目標：

改善 generated reports 與 run summaries 的品質檢查，並讓 GitHub Actions run summary 能快速呈現本次報告是否值得下載 artifact。

新增能力：

- 區分 workflow `status` 與 report `quality_status`。
- `run_summary.json` 記錄 `quality_status`、warnings、errors、`review_summary` 與 `copy_ready_report` 路徑。
- 產生 `output_quality_review.md`，包含 run id、topic、workflow status、quality status、output type、key metrics、warnings、errors 與 recommendation。
- 產生 `review_summary.md`，提供短版、適合截圖的本次報告結果摘要。
- 產生 `copy_ready_report.md`，提供可貼到 Notion、Slack、Google Docs 或簡報備註的乾淨版本。
- `outputs/index/report_index.json` 保存 quality status 與 review-ready output paths。
- weekly workflow 會寫入 GitHub Actions Step Summary，顯示 topic、run id、workflow status、quality status、warnings、artifact name 與 key files。

### Phase 9｜Notification and Review Workflow

目標：

在 weekly report 產生後，提供主動通知與可追蹤的 review workflow。

狀態：Planned

規劃方向：

- Add a notification or review workflow after weekly report generation.
- Consider GitHub issue-based weekly report records.
- Include report status, quality status, warnings, and artifact links in the review workflow.
- Keep generated reports as downloadable artifacts.

### Phase 10｜Agentic Research Planning

目標：

讓 agent plan research tasks、identify information gaps，並提出 follow-up questions。

狀態：Planned
