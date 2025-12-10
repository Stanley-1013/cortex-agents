# Neuromorphic Multi-Agent System - 協作指南

> 當你開啟新對話並需要使用這套系統時，請遵循此指南。

## 快速開始

### 恢復進行中的任務

**新對話時（不知道任務 ID）：**
```python
import sys
import os
sys.path.insert(0, os.path.expanduser('~/.claude/neuromorphic'))
from servers.memory import get_project_context, load_checkpoint

# 自動偵測專案，找到進行中任務
project = os.path.basename(os.getcwd())
context = get_project_context(project)

if context['active_tasks']:
    task = context['active_tasks'][0]
    print(f"找到任務: {task['description']} ({task['progress']})")
    # 載入詳細狀態
    checkpoint = load_checkpoint(task['id'])
elif context['suggestion']:
    print(f"建議: {context['suggestion']}")
```

**已知任務 ID 時（同一對話內）：**
```python
from servers.tasks import get_task_progress
from servers.memory import load_checkpoint

progress = get_task_progress('TASK_ID')
print(f"進度: {progress['progress']} ({progress['percentage']}%)")

checkpoint = load_checkpoint('TASK_ID')
if checkpoint:
    print(f"恢復點: {checkpoint['summary']}")
```

### 開始新任務
```python
from servers.tasks import create_task, create_subtask

# 建立主任務
task_id = create_task(
    project="PROJECT_NAME",
    description="任務描述",
    priority=8
)

# 分解子任務
subtask_1 = create_subtask(task_id, "子任務 1", assigned_agent='executor')
subtask_2 = create_subtask(task_id, "子任務 2", depends_on=[subtask_1])
```

## Agent 協作流程

### 完整執行循環

透過 Task tool 派發 agent 執行：

```
PFC (規劃) → Executor (執行) → Critic (驗證) → Memory (存經驗)
```

### Agent 角色

| Agent | subagent_type | 職責 |
|-------|---------------|------|
| **Executor** | `executor` | 執行單一任務、撰寫程式碼 |
| **Critic** | `critic` | 驗證結果、風險評估（Graph 增強） |
| **Memory** | `memory` | 記憶存取、知識管理 |
| **Researcher** | `researcher` | 資訊收集、深度研究 |
| **Drift Detector** | `drift-detector` | SSOT-Code 偏差偵測 |

### 三層記憶查詢架構 ⭐

各 Agent 啟動時會自動查詢相關記憶（已內建於各 agent 的 `.md` 定義中）：

| 層級 | 查詢類型 | 用途 |
|------|----------|------|
| **PFC** | strategy, procedure | 決定任務分解方式 |
| **Executor** | pattern, lesson | 避免重複踩坑 |
| **Critic** | pattern, standard | 比對最佳實踐 |

> 詳見 `~/.claude/neuromorphic/agents/` 下的各 agent 定義檔

### 派發範例

#### Executor 執行任務
```
Task tool 參數：
- subagent_type: executor
- prompt: |
    任務 ID: xxx
    源檔案: /path/to/source.ts
    輸出路徑: /path/to/output.test.ts

    執行步驟：
    1. 讀取源檔案
    2. 撰寫測試
    3. 執行驗證
    4. 更新 DB 狀態

    完成後回報：TASK_COMPLETED: xxx
```
> Executor 啟動時會自動查詢 pattern/lesson 記憶

#### Critic 驗證結果
```
Task tool 參數：
- subagent_type: critic
- prompt: |
    驗證對象: /path/to/output.test.ts

    驗證標準：
    1. 測試覆蓋率 >= 80%
    2. 邊界情況是否涵蓋
    3. 測試邏輯是否正確
```
> Critic 啟動時會自動查詢 quality standard 記憶

#### Memory 存經驗
```
Task tool 參數：
- subagent_type: memory
- prompt: |
    儲存學習經驗：
    - 類別: knowledge
    - 標題: xxx
    - 內容: 學習到的模式或解法
    - 重要性: 7
```

## 資料庫操作

### 任務管理 (tasks.py)

```python
from servers.tasks import (
    create_task,          # 建立主任務
    create_subtask,       # 建立子任務（可指定 requires_validation）
    get_task,             # 取得任務詳情
    update_task_status,   # 更新狀態
    get_next_task,        # 取得下一個任務
    get_task_progress,    # 取得進度
    log_agent_action,     # 記錄日誌
    # 驗證相關
    get_unvalidated_tasks,  # 取得待驗證任務
    mark_validated,         # 標記驗證狀態
    advance_task_phase,     # 推進任務階段
    get_validation_summary  # 取得驗證統計
)

# 狀態: pending, running, done, failed, blocked
# 驗證狀態: pending, approved, rejected, skipped
# 階段: execution, validation, documentation, completed
```

### 驗證循環（重要）

```python
from servers.tasks import get_unvalidated_tasks, mark_validated, get_validation_summary

# 1. 取得待驗證任務
unvalidated = get_unvalidated_tasks(parent_task_id)

# 2. 對每個任務派發 Critic
for task in unvalidated:
    # 使用 Task tool 派發 critic agent 驗證
    pass

# 3. Critic 完成後標記
mark_validated(task_id, 'approved', validator_task_id='critic_xxx')

# 4. 查看驗證統計
summary = get_validation_summary(parent_task_id)
# {'total': 26, 'approved': 20, 'rejected': 2, 'pending': 4, ...}
```

### 記憶管理 (memory.py)

```python
from servers.memory import (
    search_memory,        # 搜尋長期記憶
    store_memory,         # 儲存記憶
    get_working_memory,   # 讀取工作記憶
    set_working_memory,   # 設定工作記憶
    save_checkpoint,      # 存 checkpoint
    load_checkpoint,      # 載入 checkpoint
    add_episode           # 記錄事件
)
```

## Auto-Compact 恢復

當 auto-compact 發生後，新對話應該：

1. **檢查 CLAUDE.md** - 讀取專案的恢復指令
2. **查詢 DB** - 取得任務進度和 checkpoint
3. **繼續執行** - 從中斷點繼續

### 標準恢復流程

```python
# 1. 取得任務狀態
progress = get_task_progress('TASK_ID')

# 2. 找到 pending 任務
pending_tasks = [t for t in progress['subtasks'] if t['status'] == 'pending']

# 3. 載入 checkpoint
checkpoint = load_checkpoint('TASK_ID')

# 4. 繼續執行
for task in pending_tasks:
    # 使用 Task tool 派發 executor
    pass
```

## Micro-Nap 機制

當 context 過長時，主動觸發 Micro-Nap：

```python
from servers.memory import save_checkpoint

state = {
    'task_id': task_id,
    'completed': completed_list,
    'pending': pending_list,
    'current_phase': 'phase_2'
}

save_checkpoint(
    project='PROJECT_NAME',
    task_id=task_id,
    agent='pfc',
    state=state,
    summary='Phase 1 完成，Phase 2 進行中'
)

print(f"""
## Micro-Nap 觸發

建議開新對話繼續。恢復指令：「繼續任務 {task_id}」
""")
```

## 三層查詢 API（Facade）

### PFC 三層查詢（Story 15）
```python
from servers.facade import get_full_context, format_context_for_agent

branch = {'flow_id': 'flow.auth', 'domain_ids': ['domain.user']}
context = get_full_context(branch, project_name="PROJECT_NAME")
# context 包含: ssot, code, memory, drift

formatted = format_context_for_agent(context)
print(formatted)
```

### Drift 偵測（Story 17）
```python
from servers.drift import detect_all_drifts, get_drift_summary

project = os.path.basename(os.getcwd())
report = detect_all_drifts(project)
if report.has_drift:
    print(get_drift_summary(project))
```

### Graph 增強驗證（Story 16）
```python
from servers.facade import validate_with_graph, format_validation_report

modified_files = ['src/api/auth.py']
branch = {'flow_id': 'flow.auth'}
validation = validate_with_graph(modified_files, branch, project)
print(format_validation_report(validation))
```

## 最佳實踐

1. **並行派發** - 使用多個 Task tool 同時執行獨立任務
2. **驗證循環** - 每個 Executor 後都要 Critic 驗證
3. **存經驗** - 重要發現存到 Memory
4. **DB 更新** - 每個任務完成後更新狀態
5. **Checkpoint** - 定期存檔以防 context 溢出
6. **偏差檢查** - 重大修改前先執行 Drift 偵測

## 常用指令

- **繼續任務 {task_id}** - 恢復進行中的任務
- **查看進度 {task_id}** - 顯示任務進度
- **使用 pfc agent 規劃 {描述}** - 開始新任務規劃
