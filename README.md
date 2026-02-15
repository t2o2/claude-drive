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
- **Production validation** — validates implementation works in production, not just tests. Catches issues like path resolution, environment differences, and framework-specific gotchas before deployment.
- **Framework gotchas database** — prevents common test-production gaps (Flask paths, React imports, CORS, etc.)
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

Three phases: **Plan** (JSON plan + dual-agent review) → **Implement** (TDD per task + production validation) → **Verify** (compliance + quality review).

### Enhanced Workflow (v2)

The enhanced spec workflow includes production validation gates:

1. **Plan** - Create detailed plan with test strategy and validation criteria
2. **Implement** - TDD cycles + framework gotcha checks + production validator
3. **Verify** - Dual-agent review + full test suite + production smoke tests

See [Production Validation Framework](docs/PRODUCTION_VALIDATION.md) for details.

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
│   ├── spec-implement-v2.md         # NEW: With production validation
│   ├── spec-verify.md
│   └── comment.md
├── docs/                    # Documentation
│   └── PRODUCTION_VALIDATION.md     # NEW: Validation framework guide
├── agents/                  # Spec review subagents
│   ├── plan-challenger.md
│   ├── plan-verifier.md
│   ├── spec-reviewer-compliance.md
│   ├── spec-reviewer-quality.md
│   ├── production-validator.md      # NEW: Production environment validation
│   ├── framework-gotchas.md         # NEW: Test-production gap prevention
│   └── plan-template-enhanced.md    # NEW: Enhanced plan structure
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
