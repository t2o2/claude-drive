---
globs: "*"
---

# Verification Before Completion

## Rule
Never mark work as complete without running verification and showing actual output.

## Required Checks

### Python
```bash
uv run pytest              # tests
uv run ruff check .        # lint
uv run ruff format --check .  # format
```

### TypeScript
```bash
npx tsc --noEmit           # type check
npm test                   # tests
npx eslint .               # lint (if configured)
```

### Rust
```bash
cargo test                 # tests
cargo clippy -- -D warnings  # lint
cargo fmt --check          # format
```

## Evidence Required
- Paste actual command output in your response
- If tests fail, fix them before claiming completion
- If linting fails, fix warnings before claiming completion
- "All tests pass" without output is NOT acceptable

## Completion Gate Checklist

Before setting a task's `passes: true` or a plan's `status: "COMPLETE"`:

1. **Test evidence** — Paste EXACT command + output (minimum 3 lines). Output must contain a recognizable pass indicator:
   - Python: "passed" or "X passed"
   - TypeScript: "Tests: X passed" or "All tests passed"
   - Rust: "test result: ok"

2. **Linter evidence** — Paste EXACT linter command + output showing zero warnings

3. **Type checker evidence** — Paste EXACT type check command + output (if applicable)

4. **Before plan → COMPLETE:** All three checks (tests + linter + type checker) must appear in the SAME response with their full output

## Anti-Patterns (Do NOT do these)
- "All tests pass" without showing output
- Showing only the last line of test output
- Running tests but not pasting the output
- Marking `passes: true` after a failing test run
- Claiming "linter is clean" without running it
