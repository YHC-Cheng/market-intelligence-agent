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
