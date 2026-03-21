# Architecture

## Module Dependencies

```
debate.py ─→ config.py     (load_config)
           ─→ models.py     (init_models)
           ─→ assignment.py  (parse_role_map_override, build_final_role_map)
           ─→ prompts.py     (build_prompts)
           ─→ graph.py       (build_debate_graph)
           ─→ output.py      (assemble_markdown, generate_filename)

graph.py ──→ nodes.py       (all node factories)

nodes.py ──→ models.py      (call_model)
           ─→ assignment.py  (pick_specialist_for_round)
           ─→ output.py      (generate_raw_filepath, _sanitize_filename)
```

## Startup Sequence

```
1. load_dotenv()                          # .env → os.environ
2. cfg = load_config()                    # os.environ → DebateConfig dataclass
3. models, available = init_models(cfg)   # API key 檢查 + LangChain client 建立
4. override = parse_role_map_override()   # --role-map JSON 解析
5. role_map = build_final_role_map()      # 隨機分配 + override 合併
6. prompts = build_prompts()              # 13 個 prompt 字串
7. graph = build_debate_graph()           # StateGraph + SQLite checkpointer
8. graph.invoke(initial_state, config)    # 開始辯論
```

## Dual Output Path

### Raw `.txt` (incremental, crash-safe)
- `chair_open_node` 建立 `outputs/<short_title>_<YYYYMMDD>/debate_raw_<HHMMSS>.txt`
- 每個節點呼叫 `_append_raw()` 即時寫入（append mode）
- 即使程式崩潰，已完成的發言都保留在 raw file

### Formatted `.md` (post-completion)
- graph 結束後，`debate.py` 的 `_write_formatted_output()` 呼叫 `assemble_markdown()`
- 產出 `outputs/<short_title>_<YYYYMMDD>/debate_<HHMMSS>.md`
- 包含：header、角色表、所有發言、統計、Claim Registry、Chair 最終評估

### `write_output_node` 是 no-op
這個節點只印 log，不寫檔。真正的寫入在 `debate.py` 裡 graph 執行完之後。

## Session Persistence

### Thread ID
- 公式：`debate_<md5(topic + "_" + seed)[:8]>` (see `debate.py:make_thread_id`)
- 相同 topic + seed 永遠產生相同 thread ID

### SQLite Checkpointing
- `langgraph.checkpoint.sqlite.SqliteSaver` → `debate_checkpoints.db`
- LangGraph 在每個節點完成後自動存 checkpoint
- `--list-sessions` 查詢 `SELECT DISTINCT thread_id FROM checkpoints`

### Resume
- `graph.invoke(None, config={"configurable": {"thread_id": session_id}})`
- 傳 `None` 作為 state → LangGraph 從 checkpoint 恢復

## Interactive Continuation

`debate.py:_interactive_continuation()` 在計畫回合跑完後進入互動循環：

1. 判斷是否該暫停問使用者 (`_should_ask_continue`)
   - `total_rounds >= 9`：每回合都問
   - 否則：每 `original_rounds` 回合問一次
2. 使用者輸入 `y` → 設定新的 `max_rounds` 並注入狀態
3. **注入方式**：`graph.update_state(config, {...}, as_node="chair_summary")`
   - 必須指定 `as_node="chair_summary"` 讓條件邊重新評估
   - 注入 `max_rounds` 和 `should_continue=True`
4. `graph.invoke(None, config)` 從 checkpoint 繼續

## Output Folder Naming

```
outputs/
  <short_title>_<YYYYMMDD>/
    debate_<HHMMSS>.md          # formatted
    debate_raw_<HHMMSS>.txt     # raw
```

- `short_title` 從 Chair 開場的 `[SHORT_TITLE: ...]` 標籤解析
- 若解析失敗，fallback 到 topic 前 15 字元
- `_sanitize_filename()` 將不安全字元替換為 `_`
