# Claude Drive

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

## Context Continuation

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

## Complexity Triage

| Complexity | Criteria | Action |
|-----------|----------|--------|
| **Simple** | 1-2 files, clear fix | Execute directly |
| **Medium** | 3-4 files, well-defined | Use TaskCreate for tracking |
| **Complex** | 5+ files, new patterns, architecture | Suggest `/spec` |

## TDD: RED → GREEN → REFACTOR

When writing or modifying source code, follow this cycle:

1. **RED** — Write a failing test first. Run ONLY the specific test file. It MUST fail.
2. **GREEN** — Write minimal code to pass. Run ONLY the specific test file. It MUST pass.
3. **REFACTOR** — Clean up without changing behavior. Run full suite piped through `| tail -30`.

When TDD applies:
- **Mandatory** during `/spec` implementation phase
- **Encouraged** in quick mode for non-trivial logic
- **Skipped** for config files, scripts, documentation, trivial changes

### Fast Test Commands

| Language | Targeted (RED/GREEN) | Full Suite (REFACTOR) |
|----------|---------------------|-----------------------|
| Python | `uv run pytest tests/test_<module>.py -x 2>&1 \| tail -20` | `uv run pytest 2>&1 \| tail -30` |
| TypeScript | `npx vitest run <file>.test.ts 2>&1 \| tail -20` | `npm test 2>&1 \| tail -30` |
| Rust | `cargo test <module_name> 2>&1 \| tail -20` | `cargo test 2>&1 \| tail -30` |

Full suite: Maximum 3 times per session. Log full output to `.drive/test-output.log`.

## Verification Before Completion

**Never claim success without evidence.** Always paste actual command output.

Before setting a task's `passes: true` or a plan's `status: "COMPLETE"`:

1. **Test evidence** — EXACT command + output (minimum 3 lines) with pass indicator
2. **Linter evidence** — EXACT linter command + output showing zero warnings
3. **Type checker evidence** — EXACT type check command + output (if applicable)

Anti-patterns: "All tests pass" without output. Showing only the last line. Marking `passes: true` after a failing test.

## Coding Standards

- Core business logic = standalone library with zero external dependencies
- Domain errors in core, technical errors in adapters
- Constructor injection for dependencies
- Comments explain "why", not "what"
- Fix all lint warnings — zero tolerance
- No dead code, no commented-out code
- Structured logging at system boundaries only

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

## Session End Behavior

The `session_end.py` Stop hook runs automatically when a session ends:
1. **Auto-commit** — commits tracked file changes with a `wip: <summary>` message
2. **Progress reminder** — warns if `.drive/claude-progress.txt` wasn't updated
3. **Telegram notification** — sends a session summary if configured in `.drive/config.json`

## Telegram Feedback

Users can send tasks/feedback to the Telegram bot between sessions. On next session start, `session_start.py` polls `getUpdates` and adds new messages to `config.tasks[]`. Use `/comment` to view, work on, mark done, or dismiss tasks.

Only approved senders can submit feedback. During `/setup`, a 6-digit pairing code is generated. Send it to your bot as the first message to pair.
