# Cortex Multi-Agent System

A multi-agent task system with three-layer architecture: **Skill** (intent) + **Code Graph** (reality) + **Memory** (experience).

Works with any AI coding agent that supports custom skills/tools, including Claude Code, Cursor, Windsurf, Cline, and other LLM-based development tools.

## Installation

### Step 1: Clone Repository

**macOS/Linux:**
```bash
git clone https://github.com/Stanley-1013/cortex-agents.git ~/.claude/skills/cortex-agents
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/Stanley-1013/cortex-agents.git "$env:USERPROFILE\.claude\skills\cortex-agents"
```

**Windows (CMD):**
```cmd
git clone https://github.com/Stanley-1013/cortex-agents.git "%USERPROFILE%\.claude\skills\cortex-agents"
```

### Step 2: Run Install Script

The install script will:
- Install agent definitions to `~/.claude/agents/`
- Configure Claude Code hooks in `~/.claude/settings.json`
- Initialize the database if needed

**macOS/Linux:**
```bash
python ~/.claude/skills/cortex-agents/scripts/install.py --skip-prompts
```

**Windows:**
```cmd
python "%USERPROFILE%\.claude\skills\cortex-agents\scripts\install.py" --skip-prompts
```

Install options:
- `--skip-prompts`: Non-interactive mode (recommended for scripts)
- `--all`: Run all optional setup steps
- `--add-claude-md`: Add config to project's CLAUDE.md
- `--init-ssot`: Initialize project SSOT INDEX
- `--sync-graph`: Sync Code Graph

### Step 3: Add Skill to Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "skills": ["~/.claude/skills/cortex-agents"]
}
```

> **Note**: The install script automatically configures hooks. You only need to add the skills entry.

### For Other AI Agents (Cursor/Windsurf/etc.)

Add the skill path to your agent's configuration, or include the import in your system prompt:

```python
import sys, os
sys.path.insert(0, '/path/to/skills/cortex-agents')
```

### Verify Installation

```bash
python ~/.claude/skills/cortex-agents/scripts/doctor.py
```

## Features

- **Task Lifecycle Management**: Create, execute, validate, and document tasks with multiple agents
- **Code Graph**: AST-based code analysis for TypeScript, Python, and Go
- **Drift Detection**: Compare Skill definitions against actual code implementation
- **Semantic Memory**: FTS5 + embedding-based search with LLM reranking
- **Micro-Nap Checkpoints**: Save/resume long-running tasks across conversations

## Quick Start

```python
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/skills/cortex-agents'))

from servers.facade import sync, status, check_drift
from servers.tasks import create_task, create_subtask
from servers.memory import search_memory_semantic, store_memory
```

## Project Setup

Initialize a project Skill:

**macOS/Linux:**
```bash
python ~/.claude/skills/cortex-agents/scripts/init_project.py my-project /path/to/project
```

**Windows (CMD/PowerShell):**
```cmd
python "%USERPROFILE%\.claude\skills\cortex-agents\scripts\init_project.py" my-project C:\path\to\project
```

This creates `<project>/.claude/skills/<project-name>/SKILL.md` - a template for LLM to fill with project documentation.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Cortex System                      │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  Skill Layer │  Code Graph  │    Memory    │     Tasks      │
│   (Intent)   │  (Reality)   │ (Experience) │  (Execution)   │
├──────────────┼──────────────┼──────────────┼────────────────┤
│  SKILL.md    │  code_nodes  │  long_term   │    tasks       │
│  flows/*.md  │  code_edges  │  episodes    │  checkpoints   │
│  domains/*   │  file_hashes │  working_mem │  agent_logs    │
└──────────────┴──────────────┴──────────────┴────────────────┘
```

## Agents

| Agent | Type | Purpose |
|-------|------|---------|
| PFC | `pfc` | Planning and task decomposition |
| Executor | `executor` | Task execution |
| Critic | `critic` | Validation and quality checks |
| Memory | `memory` | Knowledge storage and retrieval |
| Researcher | `researcher` | Information gathering |
| Drift Detector | `drift-detector` | Skill-Code drift detection |

## Key APIs

### Facade (Unified Entry Point)

```python
from servers.facade import (
    sync,              # Sync Code Graph
    status,            # Project status
    check_drift,       # Skill vs Code drift
    get_full_context,  # Three-layer context
    finish_task,       # Complete task lifecycle
)
```

### Tasks

```python
from servers.tasks import (
    create_task,       # Create parent task
    create_subtask,    # Create child task with dependencies
    get_task_progress, # Get completion stats
)
```

### Memory

```python
from servers.memory import (
    search_memory_semantic,  # Semantic search with reranking
    store_memory,            # Store to long-term memory
    save_checkpoint,         # Micro-Nap checkpoint
    load_checkpoint,         # Resume from checkpoint
)
```

## Scripts

```bash
# Install/update agents, hooks, and database
python ~/.claude/skills/cortex-agents/scripts/install.py --skip-prompts

# Diagnostics (verify installation)
python ~/.claude/skills/cortex-agents/scripts/doctor.py

# Sync Code Graph for a project
python ~/.claude/skills/cortex-agents/scripts/sync.py /path/to/project

# Initialize project Skill
python ~/.claude/skills/cortex-agents/scripts/init_project.py my-project /path/to/project
```

## Documentation

- [SKILL.md](SKILL.md) - Main skill definition
- [reference/API_REFERENCE.md](reference/API_REFERENCE.md) - Complete API documentation
- [reference/WORKFLOW_GUIDE.md](reference/WORKFLOW_GUIDE.md) - Workflow patterns
- [reference/GRAPH_GUIDE.md](reference/GRAPH_GUIDE.md) - Graph operations
- [reference/TROUBLESHOOTING.md](reference/TROUBLESHOOTING.md) - Common issues

## Database

SQLite database at `~/.claude/skills/cortex-agents/brain/brain.db`

Schema: [brain/schema.sql](brain/schema.sql)

## Compatibility

| Feature | Claude Code | Other AI Agents |
|---------|-------------|-----------------|
| Memory & Semantic Search | ✅ Full | ✅ Full |
| Code Graph & Drift Detection | ✅ Full | ✅ Full |
| Task Lifecycle Management | ✅ Full | ✅ Full |
| Multi-Agent Coordination | ✅ Native (Task tool) | ⚠️ Simulated |

> **Note**: Claude Code's Task tool enables true parallel agent execution with isolated contexts. Other AI tools can use all APIs but run agents sequentially in shared context.

## Requirements

- Python 3.8+
- SQLite 3.35+ (with FTS5 support)

## License

MIT
