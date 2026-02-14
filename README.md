# Claude Drive

Framework for long-running Claude Code sessions. Tracks progress across sessions, preserves context, enforces TDD, and prevents premature completion. Includes a multi-agent system for running parallel Claude Code instances.

## Install

```bash
cd your-project
curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash
```

Overwrite an existing install:

```bash
curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | FORCE=1 bash
```

Start a Claude Code session — everything activates automatically.

## Single-Agent Usage

### First-Run Setup

On first session, you'll be prompted to run:

```
/setup
```

This asks for project name, language, TDD strictness, and optional Telegram notifications. Config saves to `.drive/config.json`.

### Daily Work

Work normally. The framework runs in the background:

- **Progress is tracked** — each session's work, decisions, and failed approaches are logged to `.drive/claude-progress.txt`. Next session starts with full context.
- **Lint output is tamed** — max 5 error lines in-context, full output in `.drive/lint-output.log`.
- **Context is monitored** — warns at 75%, auto-saves state at 88% so the next session can resume.
- **TDD is enforced** — editing source without tests triggers a reminder.
- **Session end** — auto-commits tracked file changes with a `wip:` message, optionally notifies via Telegram.

### Spec Mode

For complex features (5+ files, new architecture), use the spec workflow:

```
/spec "Add user authentication"
```

Three phases: **Plan** (JSON plan + dual-agent review) → **Implement** (TDD per task) → **Verify** (compliance + quality review).

Resume or check status:

```
/spec docs/plans/2026-02-14-auth.json
/spec
```

### Customization

Remove unused language rules after install:

```bash
rm .claude/rules/python-rules.md      # if not using Python
rm .claude/rules/typescript-rules.md   # if not using TypeScript
rm .claude/rules/rust-rules.md         # if not using Rust
```

### Telegram Notifications

Enable during `/setup` or edit `.drive/config.json`. Get a bot token from [@BotFather](https://t.me/BotFather), get your chat ID from [@userinfobot](https://t.me/userinfobot).

Send tasks to your bot between sessions — they appear on next session start. Only paired senders are processed. During `/setup`, a 6-digit pairing code is generated. Send it to your bot as the first message to pair.

Manage tasks and pairing:

```
/comment
```

## Multi-Agent Mode

Run multiple Claude Code instances in parallel, each with a specialized role, communicating via a git-synchronized task board.

### Prerequisites

- Docker Desktop
- Claude Code CLI authenticated (`claude login`) or `ANTHROPIC_API_KEY` env var

### Quick Start

```bash
# 1. Install Claude Drive into your project
cd your-project
curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash

# 2. (Optional) Edit fleet config — defaults to 2 implementers + 1 reviewer + 1 docs
#    Edit .drive/agents/config.json to change roles, counts, or model

# 3. Add tasks to the board
python3 scripts/board.py add "Implement user authentication" --priority 1
python3 scripts/board.py add "Add input validation to API endpoints" --priority 2
python3 scripts/board.py add "Write integration tests for payment flow" --priority 3

# 4. Launch agents
scripts/run-agents.sh

# 5. Monitor
scripts/agent-status.sh

# 6. Stop
scripts/stop-agents.sh
```

### Authentication

Agents need Claude CLI access. Two methods (in order of preference):

| Method | Setup | How it works |
|--------|-------|--------------|
| **Credentials file** | Run `claude login` on your machine | `~/.claude/credentials.json` is mounted read-only into each container |
| **API key** | `export ANTHROPIC_API_KEY=sk-ant-...` | Passed as env var into each container |

If `~/.claude/credentials.json` exists, it's used automatically. No extra config needed.

### Agent Roles

| Role | What it does | Modifies code? |
|------|-------------|----------------|
| **implementer** | Claims tasks, writes code with TDD, runs tests, commits | Yes |
| **reviewer** | Reviews recent commits, posts messages about issues | No |
| **docs** | Updates documentation based on recent changes | Yes (docs only) |
| **janitor** | Scans for lint/quality issues, posts messages | No |

### Fleet Config

Edit `.drive/agents/config.json`:

```json
{
  "runtime": "docker",
  "roles": [
    { "name": "implementer", "count": 2, "model": "claude-sonnet-4-5-20250929", "max_sessions": 20 },
    { "name": "reviewer", "count": 1, "model": "claude-sonnet-4-5-20250929", "max_sessions": 20 },
    { "name": "docs", "count": 1, "model": "claude-sonnet-4-5-20250929", "max_sessions": 10 }
  ]
}
```

### Task Board

Add and manage tasks from the CLI:

```bash
python3 scripts/board.py add "Fix login bug" --priority 1    # Add a task
python3 scripts/board.py list                                 # List all tasks
python3 scripts/board.py list --status open                   # Filter by status
```

Or use the interactive `/board` command inside any Claude session.

### Dashboard

A web UI for monitoring agents and managing tasks:

```bash
uv run scripts/dashboard.py          # Start on http://localhost:8000
```

Features:
- Kanban board with Open, In Progress, Done, Failed columns
- Add/delete/reopen tasks from the browser
- Agent activity with heartbeat freshness
- Inter-agent messages feed
- Auto-refreshing via htmx (no manual reload)

### Monitoring

```bash
scripts/agent-status.sh              # Fleet overview + last 5 log lines per agent
python3 scripts/board.py list        # Task status
python3 scripts/lock.py list         # Who's working on what
```

### Cost Controls

- `max_sessions` per role in config (default: 20)
- Idle detection: 5 consecutive no-op sessions → agent exits
- `scripts/stop-agents.sh` to halt all agents immediately

### DevPod (Cloud VMs)

For larger fleets (20+ agents), use DevPod instead of local Docker:

```bash
# Install DevPod CLI: https://devpod.sh
devpod provider add aws    # or gcloud, kubernetes

# Update .drive/agents/config.json:
#   "runtime": "devpod"
#   "devpod.provider": "aws"
#   "sync.upstream_remote": "git@github.com:user/repo.git"

scripts/run-agents.sh
```

| | Docker | DevPod |
|---|---|---|
| Where | Local machine | Cloud VM |
| Cost | Free | Pay-per-use |
| Scale | 3-5 agents | 20+ agents |
| Sync | Volume mount | Git SSH/HTTPS |
| Setup | Docker Desktop | `devpod` CLI + provider |

### How It Works

Each agent runs a **Ralph-loop** (infinite session cycle):

1. Clone project from upstream git repo
2. Read task board, claim highest-priority open task
3. Run a Claude Code session with role-specific prompt
4. Commit changes, sync back to upstream
5. Sleep 10s, repeat

Agents coordinate via file-based locks (`.drive/agents/locks/`) and a file-per-task board (`.drive/agents/tasks/`). Git push conflicts serve as natural lock arbitration.

### Security

- Credentials mounted read-only — agents can't modify your auth
- API keys passed via env var, never stored in project files
- Agent prompts read from upstream (immutable to agents)
- Board messages treated as data, not executable instructions

### Smoke Test

Verify the Docker setup before launching real agents:

```bash
scripts/smoke-test.sh --docker-only
```

## Supported Languages

Python (uv + ruff + pytest) · TypeScript (npm + eslint + vitest) · Rust (cargo + clippy)

## Credits

Patterns from Anthropic's engineering articles on [building a C compiler](https://www.anthropic.com/engineering/building-c-compiler) across 2000 Claude sessions and [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
