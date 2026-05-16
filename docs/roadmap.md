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
| Phase 8 | Weekly automation with GitHub Actions | Run the workflow on a weekly schedule | Planned |
| Phase 9 | Agentic research planning | Let the agent plan research tasks and identify follow-up questions | Planned |

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
