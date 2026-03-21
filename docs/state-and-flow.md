# State & Flow

## DebateState (graph.py)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `topic` | `str` | — | 辯題，啟動後不變 |
| `topic_context` | `str` | `""` | 額外背景說明 |
| `round` | `int` | `0` | 當前回合 (0=開場) |
| `max_rounds` | `int` | `3` | 最大回合數，interactive 模式下會被動態修改 |
| `role_map` | `dict` | — | `{role_key: model_key}`，啟動時設定 |
| `rng_seed` | `int` | — | 辯論 seed，specialist 選擇用 `seed + round_num` |
| `history` | `Annotated[list[SpeechRecord], operator.add]` | `[]` | **append-only**，每節點回傳新紀錄 |
| `chair_summaries` | `Annotated[list[str], operator.add]` | `[]` | Chair 歷輪摘要，用於跨輪記憶 |
| `claim_registry` | `str` | `""` | 結構化 claim 追蹤，每輪由 Chair 更新 |
| `short_title` | `str` | `""` | 輸出資料夾名，`chair_open_node` 設定一次 |
| `next_specialist` | `str` | `""` | Chair 推薦的下一輪專家 |
| `chair_directive` | `str` | `""` | Chair 給下輪的指令 (= 最近一次 chair summary) |
| `supporters_speech` | `str` | `""` | 本輪正方發言 |
| `opponents_speech` | `str` | `""` | 本輪反方發言 |
| `third_party_speech` | `str` | `""` | 本輪專家發言 |
| `supporters_response` | `str` | `""` | 正方對專家的回應 |
| `opponents_response` | `str` | `""` | 反方對專家的回應 |
| `chair_summary` | `str` | `""` | 本輪 Chair 摘要 |
| `should_continue` | `bool` | `True` | Chair 的繼續/結束決定 |
| `raw_output_path` | `str` | `""` | raw 輸出檔路徑，`chair_open_node` 設定 |

## SpeechRecord (graph.py)

```python
class SpeechRecord(TypedDict):
    round: int          # 回合數 (0=開場)
    role_zh: str        # 角色 key (e.g. "supporters", "devils_advocate")
    model_name: str     # 模型 key (e.g. "claude", "gpt4o")
    content: str        # 發言內容
    timestamp: str      # ISO 8601 timestamp
```

## Node Sequence

```
chair_open
    │
    ▼
increment_round ◄──────────────────────────────────────────┐
    │                                                       │
    ▼                                                       │
supporters                                                  │
    │                                                       │
    ▼                                                       │
opponents                                                   │
    │                                                       │
    ▼                                                       │
third_party (specialist, 每回合選一位)                        │
    │                                                       │
    ▼                                                       │
supporters_respond (100-150 words)                          │
    │                                                       │
    ▼                                                       │
opponents_respond (100-150 words)                           │
    │                                                       │
    ▼                                                       │
chair_summary ──→ [CONTINUE] → increment_round ─────────────┘
              └──→ [CONCLUDE] → write_output → END
```

### Node Constants (graph.py)

`NODE_CHAIR_OPEN`, `NODE_INCREMENT`, `NODE_SUPPORTERS`, `NODE_OPPONENTS`, `NODE_THIRD_PARTY`, `NODE_SUPPORTERS_RESPOND`, `NODE_OPPONENTS_RESPOND`, `NODE_CHAIR_SUMMARY`, `NODE_WRITE_OUTPUT`

## Conditional Routing

```python
def _route_after_summary(state: DebateState) -> str:
    if state["should_continue"] and state["round"] < state["max_rounds"]:
        return "continue_debate"    # → increment_round
    return "end_debate"             # → write_output → END
```

## Context Truncation (_build_context, nodes.py)

每個 debate 節點呼叫 `_build_context(state, current_role, cfg)` 組裝截斷後的歷史注入 prompt：

1. **Round 0 (opening)**: 永遠以 digest 形式包含 (`opening_digest_chars` = 200 chars)
2. **最近 N 輪** (`full_detail_rounds` = 2): 完整包含每個發言
3. **更早的輪次**: 每個發言截取 `summary_digest_chars` (150) chars 作為摘要
4. **Hard cap**: 總長度超過 `max_history_chars` (12000) 則截斷，附加 `[... HISTORY TRUNCATED ...]`

### Chair Summary 的額外截斷

`chair_summary_node` 注入當輪發言時有獨立的截斷限制：
- `chair_summary_sup_chars` (800): 正方發言
- `chair_summary_opp_chars` (800): 反方發言
- `chair_summary_specialist_chars` (600): 專家發言
- `chair_summary_digest_chars` (500): 過往 Chair 摘要的每條 digest
- Response 截取 400 chars (硬編碼)

## Chair Structured Tags

Chair 的輸出包含機器可讀標籤，由 `nodes.py` 中的 regex 解析：

| Tag | Parser | Where | Fallback |
|-----|--------|-------|----------|
| `[SHORT_TITLE: ...]` | `_extract_short_title` | `chair_open_node` | topic 前 15 字元 |
| `[SPECIALIST: role]` | `_extract_specialist_recommendation` | `chair_summary_node` | `""` (用 seeded random) |
| `[DECISION: CONTINUE/CONCLUDE]` | `parse_chair_decision` | `chair_summary_node` | legacy phrase match, 最終 default `True` |
| `CLAIM REGISTRY:\n- [...]` | `_extract_claim_registry` | `chair_summary_node` | 保留上一輪的 registry |

### Specialist Selection Precedence

1. Chair 的 `[SPECIALIST: role]` 推薦（若存在且合法）
2. Fallback: `pick_specialist_for_round(seed, round_num)` — `Random(seed + round_num).choice(SPECIALIST_ROLES)`

## Data Flow: Chair → Next Round

```
chair_summary_node returns:
  chair_directive = speech      ← 下輪正反方以此為指令
  chair_summaries = [speech]    ← append-only，跨輪記憶
  claim_registry = extracted    ← 注入下輪所有發言者
  next_specialist = extracted   ← third_party_node 優先使用
  should_continue = parsed      ← 條件路由判斷
```
