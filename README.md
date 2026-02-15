# Claude Drive

Framework for long-running Claude Code sessions. Tracks progress across sessions, preserves context, enforces TDD, and prevents premature completion.

## Install

Copy the `.claude/` directory into your project root. Start a Claude Code session — everything activates automatically.

## Usage

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

## Supported Languages

Python (uv + ruff + pytest) · TypeScript (npm + eslint + vitest) · Rust (cargo + clippy)

## Credits

Patterns from Anthropic's engineering articles on [building a C compiler](https://www.anthropic.com/engineering/building-c-compiler) across 2000 Claude sessions and [effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).
