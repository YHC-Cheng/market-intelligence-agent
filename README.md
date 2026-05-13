# Market Intelligence Agent

## Project Goal

Build an AI-powered workflow that automatically collects market updates, summarizes key information, evaluates relevance, and generates market analysis reports and slide drafts.

The long-term goal is to evolve this workflow into an AI Agent that can plan research tasks, collect market data, identify useful sources, summarize insights, and generate reports automatically.

## Initial Topic

AI Agent in B2B SaaS

## Initial Scope

The first version focuses on collecting and summarizing market updates from selected sources.

## Data Sources

Initial sources include:

- OpenAI Blog
- Anthropic News / Blog
- Google Cloud Blog
- AWS Blog
- Microsoft Azure Blog
- FinOps Foundation
- Vantage Blog

## Expected Outputs

The project will eventually generate:

- Market brief in Markdown
- Market analysis report in Markdown
- Slide draft in Markdown
- Source list in JSON

## Roadmap

### Phase 0: Project Setup

Set up the development environment, project folder, README, and basic Python files.

### Phase 1: Collect Article Metadata

Collect article titles, URLs, sources, and published dates.

### Phase 2: Extract Article Content

Extract and clean article content from collected URLs.

### Phase 3: Generate AI Summaries

Use AI to summarize articles and generate a market brief.

### Phase 4: Rank and Filter Sources

Evaluate relevance, credibility, novelty, actionability, and uniqueness.

### Phase 5: Generate Market Analysis Report

Turn selected sources into a structured market analysis report.

### Phase 6: Generate Slide Draft

Convert the report into a 3-5 page slide draft.

### Phase 7: Schedule Automation

Run the workflow regularly and send notifications.

### Phase 8: Add Agentic Research Planning

Allow the AI Agent to break down research goals, identify data gaps, and perform follow-up searches.

## How to Run

```bash
python3 main.py
```

Expected output:

```text
Market Intelligence Agent started.
Topic: AI Agent in B2B SaaS
```

## Validate Sources

Run:

```bash
python3 scripts/validate_sources.py
```
