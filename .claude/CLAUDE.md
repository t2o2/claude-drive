# Project Rules

## Session Init Sequence

On every session start, the `session_start.py` hook runs a deterministic init:
1. **Environment summary** — pwd, project type, last 5 git commits
2. **Progress file** — last 2 session blocks from `.drive/claude-progress.txt`
3. **Continuation file** — `.drive/sessions/continuation.md` if it exists

**Do NOT explore the codebase from scratch.** Trust the progress file and continuation context. Only explore files directly relevant to your current task.

## Progress Protocol

Maintain `.drive/claude-progress.txt` as an append-only log. At the end of each session (or when context runs low), append a block:

```
## Session YYYY-MM-DD HH:MM

### Completed
- <what was done, with file paths>

### Decisions
- <key decisions made and why>

### Failed Approaches
- <what was tried and why it failed — prevents retry loops>

### Next
- <ordered next steps for the next session>
```

Rules:
- Never delete or rewrite existing blocks — append only
- The hook injects only the last 2 blocks, so earlier history won't bloat context
- Always record failed approaches — this is critical for preventing retry loops

## Session Continuity Protocol

1. **On session start:** If `.drive/sessions/continuation.md` exists, read it immediately, follow the "Next Steps" section, then delete the file.
2. **During work:** When you receive a context warning from the context monitor hook, immediately:
   - Append a progress block to `.drive/claude-progress.txt`
   - Write `.drive/sessions/continuation.md` with: current task, completed steps, remaining steps, open questions, relevant file paths
   - Inform the user that context is running low and a continuation file has been saved
3. **Continuation file format:**
   ```markdown
   # Continuation
   ## Current Task
   <what we're doing>
   ## Completed
   - <done items>
   ## Remaining
   - <todo items>
   ## Key Files
   - <paths>
   ## Notes
   <context the next session needs>
   ```

## Workflow Modes

### Quick Mode (Default)
- Execute tasks directly without ceremony
- Use `TaskCreate`/`TaskUpdate` for work requiring 3+ steps
- If a request is complex (5+ files, new architecture, cross-cutting), suggest `/spec`

### Spec Mode (`/spec`)
- Three-phase workflow: Plan → Implement (TDD) → Verify
- Plans live in `docs/plans/` as JSON files (models resist corrupting JSON structures)
- Each phase has guardrails enforced by hooks and rules

## Test Strategy

Context is precious. Minimize test output during development:

- **During RED/GREEN cycles:** Run ONLY the specific test file, not the full suite
  - Python: `uv run pytest tests/test_<module>.py -x 2>&1 | tail -20`
  - TypeScript: `npx vitest run <file>.test.ts 2>&1 | tail -20`
  - Rust: `cargo test <module_name> 2>&1 | tail -20`
- **At phase boundaries (REFACTOR, task complete):** Run full suite, piped through `| tail -30`
- **Full suite:** Maximum 3 times per session. Log full output to `.drive/test-output.log`
- **Always pipe test output through `| tail -N`** to cap context usage

## Verification Requirements

**Never claim success without evidence.** Always:
- Run tests and show actual output
- Run type checker and show actual output
- Run linter and show actual output
- Include command + output in your response

## Language Standards

| Language | Package Manager | Linter/Formatter | Test Runner | Type Check |
|----------|----------------|-------------------|-------------|------------|
| Python | `uv` | `ruff` | `pytest` | `pyright`/type hints |
| TypeScript | `npm`/`pnpm` | `eslint`/`prettier` | `vitest`/`jest` | `tsc --noEmit` |
| Rust | `cargo` | `clippy` + `rustfmt` | `cargo test` | compiler |

## Plan File Format (JSON)

Plans are stored in `docs/plans/YYYY-MM-DD-<slug>.json`:

```json
{
  "title": "...",
  "status": "PENDING",
  "created": "YYYY-MM-DD",
  "description": "...",
  "tasks": [
    {
      "id": 1,
      "name": "...",
      "description": "...",
      "dependencies": [],
      "dod": "...",
      "files": [],
      "passes": false
    }
  ],
  "architecture_decisions": [
    {"decision": "...", "rationale": "..."}
  ],
  "risks": [
    {"risk": "...", "mitigation": "..."}
  ]
}
```

Rules:
- Use JSON, not markdown — models resist corrupting JSON structures
- Update only the `passes` field and `status` field during implementation
- Never modify `name`, `description`, or `dod` without user approval

## First-Run Setup

On first use (no `.drive/config.json`), the session start hook prompts you to run `/setup`. This command interviews the user for project name, language, TDD strictness, and optional Telegram notifications, then saves config to `.drive/config.json`.

## Telegram Feedback

Users can send tasks/feedback to the Telegram bot between sessions. On next session start, `session_start.py` polls `getUpdates` and adds new messages to `config.tasks[]`. Use `/comment` to view, work on, mark done, or dismiss tasks. Completed task count is included in session-end Telegram notifications.

### Telegram Pairing

Only approved senders can submit feedback via Telegram. During `/setup`, a 6-digit pairing code is generated and stored in `telegram.pairing_code`. The user must send this code as their first message to the bot. Once verified, their `user_id` is added to `telegram.approved_senders` and future messages are processed as tasks. Use `/comment` → "Manage pairing" to view approved senders, regenerate the code, or revoke access.

## Session End Behavior

The `session_end.py` Stop hook runs automatically when a session ends:
1. **Auto-commit** — commits tracked file changes with a `wip: <summary>` message
2. **Progress reminder** — warns if `.drive/claude-progress.txt` wasn't updated
3. **Telegram notification** — sends a session summary if configured in `.drive/config.json` (includes completed task count)

## Code Standards
- Domain errors in core, technical errors in adapters
- Constructor injection for dependencies
- Structured logging at boundaries
- Comments explain "why", not "what"
- Fix all lint warnings — zero tolerance
