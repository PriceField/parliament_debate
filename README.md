# Parliament Debate System

Multi-model AI 議會辯論系統 — 讓 Claude、GPT、Gemini、Grok 四大模型扮演不同角色，針對任意議題進行攻防式辯論。

## How It Works

系統以 [LangGraph](https://github.com/langchain-ai/langgraph) 狀態圖驅動，每輪辯論按以下順序進行：

```
主席開場 → 支持派發言 → 反對派反駁 → 第三方專家介入 → 主席總結 → (繼續/結束)
```

主席根據辯論品質決定是否繼續下一輪，或在達到最大輪數時結束。辯論結束後自動產出 Markdown 格式的完整記錄。

## Roles

| Role | 角色 | Description |
|------|------|-------------|
| Chair | 主席 | 中立主持，負責開場、指令、每輪總結與繼續/結束裁定（固定由 Claude 擔任） |
| Supporters | 支持派 | 無條件支持議題，攻擊反對派論點 |
| Opponents | 反對派 | 無條件反對議題，拆解支持派論點 |
| Devil's Advocate | 魔鬼辯護人 | 交叉質詢雙方，找出論證裂縫 |
| Risk Officer | 風險官 | 列出通過/不通過各自的風險 |
| Implementation Officer | 執行官 | 假設議題通過，分析執行層面的困難 |
| Evidence Auditor | 證據審計官 | 審計雙方的證據品質與邏輯漏洞 |
| Red Team | 紅隊 | 建構最具破壞性的失敗情境 |
| Second-Order Analyst | 二階效應分析師 | 找出雙方未考慮的連鎖效應 |
| Wild Card | 奇兵 | 提出最具顛覆性的單一觀點 |

支持派與反對派每輪固定出場；7 種專家角色每輪隨機抽一個介入，確保辯論不落入固定模式。

## Role Assignment

- **主席**固定由 Claude 擔任（`ANTHROPIC_API_KEY` 必填）
- 其餘 9 個角色在所有**已設定 API key 的模型**間隨機分配
- 保證每個可用模型至少被分配到一個角色
- 使用 `--seed` 可完全重現同一組分配

## Setup

### 1. Install dependencies

```bash
make install
```

Or manually:

```bash
pip install -r requirements.txt
```

### 2. Set API keys

```bash
make setup   # copies .env.example → .env
```

Fill in your API keys in `.env`. Only `ANTHROPIC_API_KEY` is required; the rest are optional — models without a key are automatically skipped:

```env
ANTHROPIC_API_KEY=sk-ant-...   # required (Claude is the chair)
OPENAI_API_KEY=sk-...          # optional
GOOGLE_API_KEY=AI...           # optional
XAI_API_KEY=xai-...            # optional
```

## Usage

### Basic

```bash
python debate.py --topic "AI應該受到政府監管" --rounds 3
```

### Custom role assignment

```bash
python debate.py --topic "核電應全面復興" \
  --role-map '{"supporters":"gpt4o","opponents":"gemini"}' \
  --rounds 4
```

### Reproducible run

```bash
python debate.py --topic "遠距工作應成為預設模式" --seed 42137
```

### Resume interrupted debate

```bash
python debate.py --resume debate_3a7f92c1
```

### List saved sessions

```bash
python debate.py --list-sessions
# or
make list-sessions
```

### Other make targets

```bash
make test     # ping all configured models to verify API keys and endpoints
make clean    # remove __pycache__ and SQLite checkpoint database
make run      # print usage help without running a debate
```

### All options

| Flag | Description | Default |
|------|-------------|---------|
| `--topic` | 辯題（必填，除非 `--resume` / `--list-sessions`） | — |
| `--rounds` | 最大辯論輪數 | 3 |
| `--role-map` | JSON 格式的角色→模型覆寫 | random |
| `--seed` | 隨機種子，用於重現角色分配 | random |
| `--context` | 議題的額外背景說明 | — |
| `--output` | 輸出檔名 | auto-generated |
| `--resume` | 以 session ID 恢復中斷的辯論 | — |
| `--no-interactive` | 關閉互動模式，計畫回合結束後直接結束 | — |
| `--list-sessions` | 列出所有已儲存的 session | — |

## Output

辯論過程中產出兩種檔案：

- **`debate_raw_<HHMMSS>.txt`** — 即時寫入的 raw transcript（crash-safe）
- **`debate_<HHMMSS>.md`** — 辯論結束後組裝的 Markdown 格式記錄

Markdown 檔案包含：辯題與日期、角色分配表（含 seed）、每輪完整發言、辯論統計（發言數、字數、參與模型、出場專家）、Claim Registry、Chair 最終評估。

所有輸出存放在 `outputs/<short_title>_<YYYYMMDD>/` 目錄。

## Configuration Presets

`configs/` 目錄提供 5 種預設設定：

| Preset | 用途 | 回合數 | Max tokens |
|--------|------|--------|------------|
| `configs/.env.default` | 平衡 | 3 | 1024 |
| `configs/.env.agile` | 開發/調試 | 2 | 768 |
| `configs/.env.max-quality` | 正式報告 | 5 | 2048 |
| `configs/.env.token-saver` | 節省預算 | 2 | 512 |
| `configs/.env.endless` | 長時辯論 | 20 | 1024 |

使用方式：`cp configs/.env.agile .env`

完整設定參考見 [docs/config-reference.md](docs/config-reference.md)。

## Architecture

```
debate.py        CLI entry point, argument parsing, session management
config.py        Environment-driven configuration (DebateConfig dataclass)
models.py        Model initialization (Claude, GPT, Gemini, Grok) and call wrapper
assignment.py    Role-to-model assignment with seeded randomness
prompts.py       System prompts for all 13 role/turn variants
nodes.py         LangGraph node factories (each role's turn logic)
graph.py         StateGraph definition (DebateState), routing, and compilation
output.py        Markdown output formatter and raw transcript writer
```

Checkpointing 使用 SQLite（`debate_checkpoints.db`），支援斷點續跑。

詳細架構文件見 [`docs/`](docs/) 目錄：

| Document | Content |
|----------|---------|
| [architecture.md](docs/architecture.md) | 模組相依、啟動序列、session 機制、輸出路徑 |
| [state-and-flow.md](docs/state-and-flow.md) | DebateState 欄位、節點流程、路由邏輯、context 截斷 |
| [config-reference.md](docs/config-reference.md) | 所有環境變數與預設值、preset 比較表 |
| [roles-and-prompts.md](docs/roles-and-prompts.md) | 角色定義、prompt 規則、專家輪替機制 |

## Tech Stack

- **LangGraph** — 狀態圖引擎，管理辯論流程與 checkpoint
- **LangChain** — 統一封裝 Anthropic / OpenAI / Google / xAI API
- **SQLite** — Session 持久化，支援中斷恢復
