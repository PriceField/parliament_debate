# Configuration Reference

所有設定來自環境變數（`.env` 經 `python-dotenv` 載入），映射到 `config.py:DebateConfig` dataclass。

## Model Selection

| Env Var | DebateConfig field | Default |
|---------|--------------------|---------|
| `CLAUDE_MODEL` | `claude_model` | `claude-sonnet-4-6` |
| `OPENAI_MODEL` | `openai_model` | `gpt-5.4` |
| `GOOGLE_MODEL` | `google_model` | `gemini-3-flash-preview` |
| `GROK_MODEL` | `grok_model` | `grok-3-mini` |

Model aliases (`cfg.model_aliases`): `claude`, `gpt4o`, `gemini`, `grok`

## API Keys & Endpoints

| Env Var | Required | Notes |
|---------|----------|-------|
| `ANTHROPIC_API_KEY` | **必填** | 缺少會 raise `EnvironmentError` |
| `OPENAI_API_KEY` | 選填 | 沒設 → 跳過 GPT |
| `GOOGLE_API_KEY` | 選填 | 沒設 → 跳過 Gemini |
| `XAI_API_KEY` | 選填 | 沒設 → 跳過 Grok |
| `ANTHROPIC_BASE_URL` | 選填 | 設定時使用 Bearer token auth |
| `OPENAI_BASE_URL` | 選填 | 代理 URL |
| `GOOGLE_BASE_URL` | 選填 | `client_options.api_endpoint` |
| `XAI_BASE_URL` | 選填 | 代理 URL |

## Model Behaviour

| Env Var | Field | Default | Description |
|---------|-------|---------|-------------|
| `MODEL_MAX_OUTPUT_TOKENS` | `max_output_tokens` | `1024` | 每次回覆的 max tokens |
| `MODEL_TEMPERATURE` | `temperature` | `0.7` | 創意度 0.0–1.0 |
| `MODEL_CALL_RETRIES` | `call_retries` | `3` | API 重試次數 |
| `MODEL_BACKOFF_BASE` | `backoff_base` | `2` | 重試等待秒數 (`base^attempt`) |

## Debate Settings

| Env Var | Field | Default | Description |
|---------|-------|---------|-------------|
| `DEBATE_DEFAULT_ROUNDS` | `default_rounds` | `3` | 預設回合數 (`--rounds` 覆寫) |
| `DEBATE_INTERACTIVE` | `interactive` | `true` | 計畫回合結束後問使用者是否繼續 |
| `DEBATE_CHECKPOINT_DB` | `checkpoint_db` | `debate_checkpoints.db` | SQLite checkpoint 路徑 |

`DEBATE_INTERACTIVE` 接受 `true/1/yes` (case-insensitive)。CLI 的 `--no-interactive` flag 在 runtime 覆寫。

## Context Truncation

| Env Var | Field | Default | Description |
|---------|-------|---------|-------------|
| `DEBATE_MAX_HISTORY_CHARS` | `max_history_chars` | `12000` | `_build_context` 的 hard cap |
| `DEBATE_OPENING_DIGEST_CHARS` | `opening_digest_chars` | `200` | 開場 digest 長度 |
| `DEBATE_SUMMARY_DIGEST_CHARS` | `summary_digest_chars` | `150` | 早期回合每條發言的 digest |
| `DEBATE_FULL_DETAIL_ROUNDS` | `full_detail_rounds` | `2` | 最近 N 輪完整顯示 |
| `CHAIR_SUMMARY_SUP_CHARS` | `chair_summary_sup_chars` | `800` | Chair 摘要中正方截斷 |
| `CHAIR_SUMMARY_OPP_CHARS` | `chair_summary_opp_chars` | `800` | Chair 摘要中反方截斷 |
| `CHAIR_SUMMARY_SPECIALIST_CHARS` | `chair_summary_specialist_chars` | `600` | Chair 摘要中專家截斷 |
| `CHAIR_SUMMARY_DIGEST_CHARS` | `chair_summary_digest_chars` | `500` | Chair 過往摘要 per-entry digest |

## Output

| Env Var | Field | Default | Description |
|---------|-------|---------|-------------|
| `DEBATE_OUTPUT_DIR` | `output_dir` | `outputs` | 輸出根目錄 |
| `DEBATE_FILENAME_TOPIC_CHARS` | `filename_topic_chars` | `30` | fallback 檔名中的 topic 字元數 |

## Preset Configs

`configs/` 目錄包含 5 個預設設定檔。使用方式：`cp configs/.env.agile .env`

| Setting | default | agile | max-quality | token-saver | endless |
|---------|---------|-------|-------------|-------------|---------|
| `MODEL_MAX_OUTPUT_TOKENS` | 1024 | 768 | 2048 | 512 | 1024 |
| `MODEL_TEMPERATURE` | 0.7 | 0.8 | 0.7 | 0.5 | 0.6 |
| `DEBATE_DEFAULT_ROUNDS` | 3 | 2 | 5 | 2 | 20 |
| `DEBATE_INTERACTIVE` | true | true | true | true | false |
| `DEBATE_MAX_HISTORY_CHARS` | 12000 | 8000 | 24000 | 6000 | 8000 |
| `DEBATE_FULL_DETAIL_ROUNDS` | 2 | 1 | 3 | 1 | 1 |
| `MODEL_CALL_RETRIES` | 3 | 2 | 3 | 2 | 5 |
| Use case | 平衡 | 開發/調試 | 正式報告 | 節省預算 | 長時辯論 |
