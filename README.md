# Long-Running Claude Code Framework

A battle-tested framework for running long, autonomous Claude Code sessions without losing context or progress. Built on patterns from Anthropic's engineering articles on building a C compiler across 2000 sessions and effective harnesses for long-running agents.

## What It Solves

Long Claude Code sessions suffer from:

- **Context blindness** — earlier work forgotten as the context window fills
- **Retry loops** — repeating failed approaches because there's no memory of what didn't work
- **Wasted context on noise** — full linter output and test suites eating precious tokens
- **Premature completion** — marking tasks done without actual evidence
- **Lost progress** — session ends and the next one starts from scratch

This framework fixes all of that.

## Quick Start

```bash
cd your-project
curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash
```

This downloads the framework into `.claude/`, creates the `.drive/` runtime directory, and updates your `.gitignore`. Start a Claude Code session — the hooks activate automatically.

To overwrite an existing installation:

```bash
FORCE=1 curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash
```

## How It Works

### Session Memory

Every session appends to `.drive/claude-progress.txt` — an append-only log that tracks what was done, decisions made, failed approaches, and next steps. On startup, the last 2 session blocks are automatically injected into context.

```
## Session 2026-02-14 10:30

### Completed
- Implemented user auth with JWT tokens

### Decisions
- Chose bcrypt over argon2 for password hashing (broader library support)

### Failed Approaches
- Tried session-based auth first, abandoned due to stateless API requirement

### Next
- Add refresh token rotation
- Write integration tests for auth endpoints
```

### Deterministic Startup

The `session_start.py` hook runs on every session start with a fixed sequence:

1. **Environment summary** — project directory, type (Python/TS/Rust), last 5 git commits
2. **Progress file** — last 2 session blocks from the progress log
3. **Continuation file** — emergency handoff state if the previous session ran out of context

No wasted context on codebase exploration. The session starts informed.

### Context-Preserving Output

**Linter output** (`file_checker.py`) is truncated to 5 error lines with full output logged to `.drive/lint-output.log`. Every line is prefixed with `ERROR:` for machine parseability.

**Test output** is piped through `| tail -20` during development. Full suites run at most 3 times per session, with output logged to `.drive/test-output.log`.

**Context monitor** (`context_monitor.py`) counts tool exchanges in the transcript. Warns at 75% usage, goes critical at 88% — triggering an automatic state dump before context runs out.

### Spec-Driven Development

For complex features, the `/spec` command runs a three-phase workflow:

```
/spec "Add user authentication"
```

**Phase 1 — Plan:** Creates a JSON plan file in `docs/plans/`. Two review agents (verifier + challenger) run in parallel to catch blind spots. JSON format chosen because models resist corrupting JSON structures — unlike markdown checkboxes.

**Phase 2 — Implement:** Strict TDD with targeted tests. Each task follows RED → GREEN → REFACTOR. A completion gate requires exact command output with pass indicators before marking any task done.

**Phase 3 — Verify:** Dual-agent review (compliance + quality) plus full verification suite. Issues triaged by severity and fixed before the plan is marked VERIFIED.

### TDD Enforcement

The `tdd_enforcer.py` hook fires on every file edit. If you modify a source file without a corresponding test file, it reminds you to write the test first.

During RED/GREEN cycles, only the targeted test file runs — not the full suite:

| Language | Targeted Test | Full Suite |
|----------|--------------|------------|
| Python | `uv run pytest tests/test_auth.py -x 2>&1 \| tail -20` | `uv run pytest 2>&1 \| tail -30` |
| TypeScript | `npx vitest run auth.test.ts 2>&1 \| tail -20` | `npm test 2>&1 \| tail -30` |
| Rust | `cargo test auth 2>&1 \| tail -20` | `cargo test 2>&1 \| tail -30` |

### Premature Completion Prevention

Work is never marked complete without evidence. The verification rules require:

- Exact test command + output (minimum 3 lines) with a recognizable pass indicator
- Linter command + output showing zero warnings
- Type checker output (where applicable)
- All three in the same response before a plan can move to COMPLETE

## Project Structure

```
.claude/
├── CLAUDE.md                  # Core instructions (progress, testing, plans)
├── settings.json              # Hook configuration
├── hooks/
│   ├── session_start.py       # Deterministic init: env + progress + continuation
│   ├── file_checker.py        # Truncated lint output with ERROR: prefix
│   ├── context_monitor.py     # Tool-count based context tracking
│   └── tdd_enforcer.py        # Reminds you to write tests first
├── commands/
│   ├── spec.md                # /spec dispatcher (routes by plan status)
│   ├── spec-plan.md           # Phase 1: JSON plan creation
│   ├── spec-implement.md      # Phase 2: TDD with fast tests
│   └── spec-verify.md         # Phase 3: dual-agent verification
├── agents/
│   ├── plan-verifier.md       # Validates plan completeness + JSON schema
│   ├── plan-challenger.md     # Adversarial review for blind spots
│   ├── spec-reviewer-compliance.md  # Implementation matches plan?
│   └── spec-reviewer-quality.md     # Code quality, security, performance
└── rules/
    ├── coding-standards.md    # Architecture + quality standards
    ├── tdd-enforcement.md     # RED/GREEN/REFACTOR + fast test commands
    ├── verification-before-completion.md  # Completion gate checklist
    ├── context-continuation.md  # Context handoff protocol
    ├── workflow-enforcement.md  # Task tracking + complexity triage
    ├── python-rules.md        # Python-specific standards
    ├── typescript-rules.md    # TypeScript-specific standards
    └── rust-rules.md          # Rust-specific standards

.drive/                        # Runtime state (gitignored)
├── claude-progress.txt        # Append-only session history
├── sessions/
│   └── continuation.md        # Emergency context handoff
├── lint-output.log            # Full linter output
└── test-output.log            # Full test suite output

docs/plans/                    # JSON spec plans (committed)
└── 2026-02-14-feature.json
```

## Supported Languages

| Language | Package Manager | Linter | Test Runner |
|----------|----------------|--------|-------------|
| Python | uv | ruff | pytest |
| TypeScript | npm/pnpm | eslint + prettier | vitest/jest |
| Rust | cargo | clippy + rustfmt | cargo test |

## Key Design Decisions

**JSON plans over markdown** — Models resist corrupting JSON structures. Markdown checkboxes are trivially corrupted when toggling task status. JSON plans have a `passes` boolean field that changes independently of task descriptions.

**Append-only progress** — Never rewrite history. Failed approaches are recorded explicitly to prevent retry loops across sessions.

**Truncated output with log files** — Context is the scarcest resource. Show 5 error lines in-context, log the full output to disk for reference.

**Tool-count context monitoring** — File size is an unreliable proxy for context usage. Counting `"tool_use"` occurrences in the transcript directly measures exchanges, with typical exhaustion around 100.

**Targeted tests during development** — Running the full test suite during RED/GREEN cycles wastes enormous context. Targeted tests preserve tokens for coding. Full suite runs only at phase boundaries.

## Credits

Patterns adapted from:
- [Building a C Compiler with Claude](https://www.anthropic.com) — 2000 sessions, 2B tokens
- [Effective Harnesses for Long-Running Agents](https://www.anthropic.com) — progress tracking, JSON specs, deterministic init
