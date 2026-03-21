# Roles & Prompts

## All Roles

| Key | Display Name | 類型 | 每輪出場 | 字數目標 |
|-----|-------------|------|---------|---------|
| `chair` | Chair | 主席 | 每輪 (open + summary) | ~200 |
| `supporters` | Supporters | 正方 | 每輪 (speech + response) | 200-300 / 100-150 |
| `opponents` | Opponents | 反方 | 每輪 (speech + response) | 200-300 / 100-150 |
| `devils_advocate` | Devil's Advocate | 專家 | 隨機選一 | ~200 |
| `risk_officer` | Risk Officer | 專家 | 隨機選一 | ~250 |
| `implementation_officer` | Implementation Officer | 專家 | 隨機選一 | ~250 |
| `evidence_auditor` | Evidence Auditor | 專家 | 隨機選一 | ~250 |
| `red_team` | Red Team | 專家 | 隨機選一 | ~200 |
| `second_order_analyst` | Second-Order Analyst | 專家 | 隨機選一 | ~250 |
| `wild_card` | Wild Card | 專家 | 隨機選一 | ~200 |

### Prompt-only keys (非角色，只有 prompt)

- `chair_open` — Chair 的開場 prompt
- `chair_summary` — Chair 的摘要 prompt
- `supporters_respond` — 正方對專家的回應 prompt
- `opponents_respond` — 反方對專家的回應 prompt

`build_prompts()` 回傳 13 個 key (10 角色 + 3 extra prompt keys)。

## Role Assignment Rules (assignment.py)

### Chair
- **永遠是 Claude**（硬編碼 `{"chair": "claude"}`）

### Assignable Roles
`ASSIGNABLE_ROLES` = 所有角色扣掉 chair = 9 個

### `assign_roles(available_models, seed)`
1. **Phase 1**: 保證每個 available model 至少分到一個角色
   - Shuffle models 和 roles，一對一配對
2. **Phase 2**: 剩餘角色隨機從 available models 中抽
3. 回傳 `{role_key: model_key}`

### `build_final_role_map(override, available_models, seed)`
- `override` 來自 `--role-map` JSON（`parse_role_map_override` 解析）
- 合併方式：`{**random_assignment, **override}`（override 優先）
- Validation: 所有 specialist roles 必須存在於最終 map

### Override Format
```bash
--role-map '{"supporters":"gpt4o","opponents":"gemini"}'
```
- Key: role key (必須在 `DEBATE_ROLES` 中)
- Value: model alias (必須在 `ALL_MODELS` = `["claude", "gpt4o", "gemini", "grok"]` 中)

## Specialist Rotation

`SPECIALIST_ROLES` = `["devils_advocate", "risk_officer", "implementation_officer", "evidence_auditor", "red_team", "second_order_analyst", "wild_card"]` (7 個)

### 選擇邏輯 (nodes.py:third_party_node)
1. 優先用 Chair 的 `[SPECIALIST: role]` 推薦（必須存在於 `role_map` 且有對應 prompt）
2. Fallback: `pick_specialist_for_round(seed, round_num)` = `Random(seed + round_num).choice(SPECIALIST_ROLES)`

### Determinism
- 相同 seed + round_num → 相同 specialist（除非 Chair 推薦覆寫）

## Role Descriptions

### Chair (Opening — `chair_open`)
- 中立主持，無立場
- 框架辯題、辨認最具爭議的假設
- 給正反方 Round 1 的具體指令
- 宣布本輪的 specialist
- 必須輸出 `[SHORT_TITLE: ...]`

### Chair (Summary — `chair_summary`)
- 辨識本輪最尖銳的未解決爭議
- 評估哪些論點增強/削弱
- 發出下輪指令
- 維護 Claim Registry（`[SUP-N]`, `[OPP-N]`, `[SP-N]` 格式，最多 10 條）
- 推薦下輪 specialist `[SPECIALIST: role]`
- 結尾必須輸出 `[DECISION: CONTINUE]` 或 `[DECISION: CONCLUDE]`

### Supporters (`supporters`)
- 無條件支持議題
- Round 2+ 先拆解反方最弱論點
- 提出新論點，結尾對反方發出挑戰
- 禁用語：However, On the other hand, While X is true, It's complicated

### Opponents (`opponents`)
- 無條件反對議題
- 先辨識正方的邏輯缺陷
- Steelman 正方最強論點再擊破
- 提出自己的正面反對理由
- 禁用語同正方

### Supporters' Response (`supporters_respond`)
- 100-150 words
- 只回應專家的介入，不重述立場
- 禁止忽略介入直接回到原論點

### Opponents' Response (`opponents_respond`)
- 100-150 words
- 回應專家介入 + 批評正方的回應
- 若正方讓步則追擊，若正方迴避則點名

### Devil's Advocate
- 不站邊，交叉質詢雙方
- 對本輪較強的一方刻意對立
- 找出雙方都未觸及的問題

### Risk Officer
- 列出 3 個 PASS risks + 3 個 FAIL risks
- 結構化格式：Type / Probability / Severity / Already addressed
- 不評論議題好壞

### Implementation Officer
- 假設議題通過，分析 3 個最難的執行挑戰
- 涵蓋 cost, timeline, institutional capacity
- 不評論議題好壞

### Evidence Auditor
- 4 類審計：contested facts / missing sources / misleading analogies / one solid claim per side
- 不對議題表態，但對證據品質表態

### Red Team
- 建構最具可信度的災難性 misuse/backfire 情境
- 結構化：Actors / Mechanism / Timeline / Why not obvious
- 只做 stress-testing，不平衡正面

### Second-Order Analyst
- 3 個二階/三階效應（雙方都未提及的）
- 結構化：Mechanism / Who affected / Timeframe / Reversibility
- 必須有清晰的因果鏈

### Wild Card
- 單一最具顛覆性的介入
- 可以是：重新框架辯題、跨領域洞見、第三條路、共享未質疑假設
- 必須嚴肅且有實質內容

## Display Names (output.py:ROLE_DISPLAY_NAMES)

```python
{
    "chair": "Chair",
    "supporters": "Supporters",
    "opponents": "Opponents",
    "devils_advocate": "Devil's Advocate",
    "risk_officer": "Risk Officer",
    "implementation_officer": "Implementation Officer",
    "evidence_auditor": "Evidence Auditor",
    "red_team": "Red Team",
    "second_order_analyst": "Second-Order Analyst",
    "wild_card": "Wild Card",
    "supporters_response": "Supporters' Response",
    "opponents_response": "Opponents' Response",
}
```
