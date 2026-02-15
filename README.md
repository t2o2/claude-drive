# Claude Drive

Claude Code plugin for long-running sessions. Tracks progress across sessions, preserves context, enforces TDD, and prevents premature completion.

## Install

```bash
claude plugin install claude-drive@t2o2/claude-drive
```

Or test locally during development:

```bash
claude --plugin-dir /path/to/claude-drive
```

Start a Claude Code session — everything activates automatically.

## What It Does

- **Progress tracking** — each session's work, decisions, and failed approaches are logged to `.drive/claude-progress.txt`. Next session starts with full context.
- **Context continuity** — warns at 75% context usage, auto-saves state at 88% so the next session can resume seamlessly.
- **TDD enforcement** — editing source without tests triggers a reminder.
- **Auto-commit** — session end commits tracked file changes with a `wip:` message.
- **Telegram notifications** — optional session summaries and task intake between sessions.

## Commands

| Command | Description |
|---------|-------------|
| `/setup` | First-run config — project name, language, TDD strictness, Telegram |
| `/spec` | Spec-driven development: Plan → Implement (TDD) → Verify |
| `/comment` | View and manage Telegram feedback/tasks |

## Spec Mode

For complex features (5+ files, new architecture):

```
/spec "Add user authentication"
```

Three phases: **Plan** (JSON plan + dual-agent review) → **Implement** (TDD per task) → **Verify** (compliance + quality review).

## Plugin Structure

```
claude-drive/
├── .claude-plugin/
│   └── plugin.json          # Plugin manifest
├── commands/                # Slash commands
│   ├── setup.md
│   ├── spec.md
│   ├── spec-plan.md
│   ├── spec-implement.md
│   ├── spec-verify.md
│   └── comment.md
├── agents/                  # Spec review subagents
│   ├── plan-challenger.md
│   ├── plan-verifier.md
│   ├── spec-reviewer-compliance.md
│   └── spec-reviewer-quality.md
├── hooks/                   # Lifecycle hooks
│   ├── hooks.json
│   ├── session_start.py
│   ├── session_end.py
│   ├── context_monitor.py
│   ├── tdd_enforcer.py
│   └── file_checker.py
├── CLAUDE.md                # Rules and conventions
├── LICENSE
└── README.md
```

## Supported Languages

Python (uv + ruff + pytest) · TypeScript (npm + eslint + vitest) · Rust (cargo + clippy)

## Credits

Patterns from Anthropic's articles on [building a C compiler](https://www.anthropic.com/engineering/building-c-compiler) across 2000 Claude sessions and [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
