# Slide Draft: AI

## Slide 1：本週市場趨勢 / 新趨勢

### 核心訊息
AI 正從單純的「生成式對話」轉向高度整合且垂直產業化的「代理型 AI (Agentic AI)」。

### 重點內容
- **代理型 AI 邁向垂直化與產業化：** 雲端巨頭不再僅提供通用工具，而是針對供應鏈、招募、醫療等特定領域推出專門的代理解決方案 [來源 3]。
- **克服遺留系統的「API 斷層」：** 透過虛擬桌面技術，讓 AI 代理能以電腦視覺操作缺乏 API 的老舊軟體，解決 75% 組織面臨的資產現代化難題 [來源 1]。
- **基礎設施通訊標準確立：** Model Context Protocol (MCP) 正成為 AI 代理存取雲端資源、工具與數據的標準化安全協定 [來源 1, 2]。
- **前沿模型與平台深度綁定：** 如 GPT-5 系列等頂尖模型被整合進雲端生產環境（如 Amazon Bedrock），並疊加企業級安全控管 [來源 3]。

### 講稿提示
本頁重點在於強調 AI 已進入「執行期」。我們觀察到市場正從單純的 LLM 模型競爭，轉向如何讓 AI 代理真正進入產業工作流，並透過 MCP 等標準協定解決老舊系統與安全性問題。

---

## Slide 2：市場問題與現有解法

### 核心訊息
企業面臨 AI 無法介入老舊系統、即時權限控管風險以及沈重行政負擔等三大痛點。

### 重點內容
- **遺留資產脫節：** 核心業務流程卡在無 API 的舊系統。現透過「Amazon WorkSpaces AI Agents」提供受控虛擬桌面，讓 AI 像人一樣操作 UI 進行自動化 [來源 1]。
- **權限與知識時效風險：** 模型知識過時且權限過大易出錯。現由「AWS MCP Server」提供受管理橋樑，讓代理依循最佳實踐執行 API 操作並確保安全性 [來源 2]。
- **特定產業效率瓶頸：** 醫療或供應鏈等場景存在大量非結構化行政負擔。現由 Amazon Connect 代理家族提供自動化臨床紀錄與決策方案來解決 [來源 3]。

### 講稿提示
在介紹這張投影片時，請強調「解決阻礙」的概念。過去 AI 難以落地的原因是無法與舊系統連動及安全風險，現在的解法是透過虛擬桌面模擬與標準化的通訊協定來跨越這些門檻。

---

## Slide 3：代表性 Use Case / 工具案例

### 核心訊息
目前的技術已能支持 AI 代理在藥局自動化、雲端資源管理及垂直產業場景中的實際運作。

### 重點內容
- **醫療藥局自動化：** AI 代理在 WorkSpaces 環境中透過電腦視覺跨 UI 操作病患紀錄與藥品資料庫，無需昂貴的後端 API 整合工程 [來源 1]。
- **安全雲端基礎設施操作：** 透過 AWS MCP Server 讓代理安全執行 15,000 項 AWS API，並在沙盒中執行腳本以降低 Token 消耗與延遲 [來源 2]。
- **端到端產業應用：** Amazon Connect 實現醫療文件自動產出與供應鏈決策自動化，顯示 AI 正從單點任務轉向完整流程處理 [來源 3]。

### 講稿提示
請利用這些具體案例來說明 AI 代理已不再是概念。重點分享「藥局自動化」如何避開 API 開發成本，以及「MCP Server」如何在提升效率的同時控制運行成本（COGS）。

---

## Slide 4：給產品的啟示與後續觀察

### 核心訊息
產品策略應轉向「代理原生 (Agent-native)」治理，並將降低 Legacy 整合門檻與運行成本視為競爭優勢。

### 重點內容
- **建構代理原生治理機制：** Cloud Management 產品應整合 MCP 稽核，精確區分「代理」與「人類」行為，並提供專屬權限邊界管理 [來源 2]。
- **低成本 Legacy 整合路徑：** 針對 FinOps 或 ERP 工具，可考慮提供「桌面代理介面」而非強求 API 串接，以縮短產品導入價值時間 (Time-to-Value) [來源 1]。
- **內建動態知識架構：** 產品助理應整合類似 MCP 的架構，即時檢索最新文檔與 API 規範，避免給出過時建議 [來源 2]。
- **優化運行成本 (COGS)：** 導入沙盒化腳本執行以減少 LLM 調用量，並利用新一代高效能實例（如 8th-gen EC2）提升效能 [來源 2, 3]。
- **待追蹤議題：** 持續觀察 MCP 協定在開源社群與其他雲端商間的普及度，這將決定跨雲 AI 治理的標準路徑 [來源 1]。

### 講稿提示
結尾時，請對產品團隊提出行動建議。我們不應只看 AI 的生成能力，而要將重點放在「如何管理 AI 的行為」以及「如何利用新技術降低 AI 的運行與開發成本」。

---

## References

[來源 1] Modernize your workflows: Amazon WorkSpaces now gives AI agents their own desktop (preview)  
- Source: AWS Blog RSS
- Published date: 2026-05-05
- URL: https://aws.amazon.com/blogs/aws/modernize-your-workflows-amazon-workspaces-now-gives-ai-agents-their-own-desktop-preview/

[來源 2] The AWS MCP Server is now generally available  
- Source: AWS Blog RSS
- Published date: 2026-05-06
- URL: https://aws.amazon.com/blogs/aws/the-aws-mcp-server-is-now-generally-available/

[來源 3] AWS Weekly Roundup: What’s Next with AWS 2026, Amazon Quick, OpenAI partnership, and more (May 4, 2026)  
- Source: AWS Blog RSS
- Published date: 2026-05-04
- URL: https://aws.amazon.com/blogs/aws/aws-weekly-roundup-whats-next-with-aws-2026-amazon-quick-openai-partnership-and-more-may-4-2026/