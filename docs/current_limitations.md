# Current Limitations

## 1. Web Source Support

目前 web sources 只會被分類並 skipped，尚未支援解析。

## 2. Gemini Quota

目前使用 Gemini API，free tier 可能遇到 quota 或 rate limit，因此設定 `MAX_ARTICLES_PER_RUN = 3`。

## 3. JSON Cache

目前 cache 使用 JSON 檔案，適合 MVP。若文章數超過數百或一千筆，未來建議改成 SQLite。

## 4. Markdown Output

目前報告與簡報草稿皆為 Markdown，尚未自動產出 PPTX。

## 5. LLM Provider

目前 `GeminiProvider` 已實作，`OpenAIProvider` 仍是 placeholder。
