# Claude Drive

Framework for long-running Claude Code sessions. Tracks progress across sessions, preserves context, enforces TDD, and prevents premature completion.

## Install

```bash
cd your-project
curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash
```

Overwrite an existing install:

```bash
FORCE=1 curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash
```

Start a Claude Code session — everything activates automatically.

## Usage

### Daily Work

Work normally. The framework runs in the background:

- **Progress is tracked** — each session's work, decisions, and failed approaches are logged to `.drive/claude-progress.txt`. Next session starts with full context.
- **Lint output is tamed** — max 5 error lines in-context, full output in `.drive/lint-output.log`.
- **Context is monitored** — warns at 75%, auto-saves state at 88% so the next session can resume.
- **TDD is enforced** — editing source without tests triggers a reminder.

### Spec Mode

For complex features (5+ files, new architecture), use the spec workflow:

```
/spec "Add user authentication"
```

Three phases run in sequence:

1. **Plan** — creates a JSON plan in `docs/plans/`, reviewed by two agents in parallel
2. **Implement** — TDD with targeted tests per task, completion gate requires actual test output
3. **Verify** — dual-agent review (compliance + quality), full verification suite

Resume an existing spec:

```
/spec docs/plans/2026-02-14-auth.json
```

Check spec status:

```
/spec
```

### Customization

After install, remove language rules you don't need:

```bash
rm .claude/rules/python-rules.md      # if not using Python
rm .claude/rules/typescript-rules.md   # if not using TypeScript
rm .claude/rules/rust-rules.md         # if not using Rust
```

Tune context thresholds in `.claude/hooks/context_monitor.py` (`MAX_EXCHANGES`).

Tune lint timeout in `.claude/settings.json`.

## Supported Languages

Python (uv + ruff + pytest) · TypeScript (npm + eslint + vitest) · Rust (cargo + clippy)

## Credits

Patterns from Anthropic's engineering articles on [building a C compiler](https://www.anthropic.com) across 2000 Claude sessions and [effective harnesses for long-running agents](https://www.anthropic.com).
