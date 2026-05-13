# Slide Draft: AI

## Slide 1：本週市場趨勢 / 新趨勢

### 核心訊息

AI 正從對話轉向主動代理，並邁向垂直產業落地與通訊標準化。

### 重點內容

- 雲端巨頭推動 AI 代理垂直化，鎖定供應鏈與醫療等特定流程 [來源 3]。
- 市場確立 MCP 標準，讓代理能安全存取萬項雲端資源 [來源 1, 2]。
- 雲端平台與頂尖模型深度綁定，提供企業級安全控管與效能 [來源 3]。
- AI 代理開始具備操作虛擬桌面的能力，打破老舊系統的 API 限制 [來源 1]。

### 講稿提示

這週的市場訊號非常明確：AI 不再只是聊天機器人，而是進化為能執行任務的「代理人」。我們看到產業正透過 MCP 協議建立標準化通訊，並將 AI 應用從通用型工具轉向深度的產業垂直整合。

---

## Slide 2：市場問題與現有解法

### 核心訊息

企業面臨老舊系統無 API 與 AI 權限管控風險，市場正推出安全代理方案。

### 重點內容

- 七成以上遺留系統缺乏 API，導致 AI 自動化難以介入核心流程 [來源 1]。
- AI 代理直接操作雲端資源存在安全風險，且模型知識更新緩慢 [來源 2]。
- 透過「虛擬桌面代理」技術，讓 AI 能像人一樣操作老舊軟體介面 [來源 1]。
- MCP Server 提供受管橋樑，確保 AI 執行 API 符合安全規範 [來源 2]。

### 講稿提示

企業導入 AI 的最大痛點在於「老舊資產無法串接」以及「代理行為不可控」。目前的解法是透過虛擬桌面讓 AI 直接操作 UI，並利用像 MCP 這樣的安全協議來規範 AI 的權限，解決技術斷層。

---

## Slide 3：代表性 Use Case / 工具案例

### 核心訊息

AI 代理已具備跨系統操作與專業決策能力，實現端到端的流程自動化。

### 重點內容

- 醫療人員可利用 AI 代理自動產出臨床文件，減少行政作業負擔 [來源 3]。
- AI 透過虛擬桌面跨軟體操作病患紀錄，無需重新開發系統介接 [來源 1]。
- 供應鏈主管可運用專屬 AI 進行決策分析，優化資源調度與效率 [來源 3]。
- 開發者透過 MCP 沙盒執行腳本，降低 Token 消耗並加速 API 調用 [來源 2]。

### 講稿提示

這些案例證明了 AI 代理已能進入專業領域。無論是醫療文件的自動產出，還是免 API 整合的操作舊軟體，都顯示出市場對「能直接解決複雜流程」的產品需求極高，這正是我們產品可以驗證的方向。

---

## Slide 4：給產品的啟示與後續觀察

### 核心訊息

產品開發應聚焦代理行為治理、遺留系統兼容性與規模化成本控管。

### 重點內容

- Agent Governance：整合稽核機制，區分代理與人類行為並控管權限邊界 [來源 2]。
- Workflow Integration：透過桌面代理技術，降低與客戶老舊系統整合的難度 [來源 1]。
- Cost & Reliability：利用沙盒腳本與新一代硬體，降低運行成本與模型延遲 [來源 2, 3]。

### 講稿提示

針對這三點啟示，我們的產品必須建立明確的 AI 行為審計，並思考如何利用桌面代理技術快速切入遺留系統市場。同時，透過優化腳本執行邏輯來控制營運成本，才能確保 AI 功能在規模化後的商業可行性。

---

## References

[來源 1] Modernize your workflows: Amazon WorkSpaces now gives AI agents their own desktop (preview)
- Source: AWS Blog RSS
- Category: cloud_provider
- Recommendation: Core
- Published date: 2026-05-05
- URL: https://aws.amazon.com/blogs/aws/modernize-your-workflows-amazon-workspaces-now-gives-ai-agents-their-own-desktop-preview/

[來源 2] The AWS MCP Server is now generally available
- Source: AWS Blog RSS
- Category: cloud_provider
- Recommendation: Core
- Published date: 2026-05-06
- URL: https://aws.amazon.com/blogs/aws/the-aws-mcp-server-is-now-generally-available/

[來源 3] AWS Weekly Roundup: What’s Next with AWS 2026, Amazon Quick, OpenAI partnership, and more (May 4, 2026)
- Source: AWS Blog RSS
- Category: cloud_provider
- Recommendation: Core
- Published date: 2026-05-04
- URL: https://aws.amazon.com/blogs/aws/aws-weekly-roundup-whats-next-with-aws-2026-amazon-quick-openai-partnership-and-more-may-4-2026/