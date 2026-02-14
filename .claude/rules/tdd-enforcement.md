---
globs: "*.py,*.ts,*.tsx,*.rs"
---

# TDD Enforcement

## RED → GREEN → REFACTOR

When writing or modifying source code, follow this cycle:

### 1. RED — Write a failing test first
- Create test that describes expected behavior
- Run ONLY the specific test file (not the full suite)
- It MUST fail — show the failing output

### 2. GREEN — Write minimal code to pass
- Implement only enough to make the test pass
- Run ONLY the specific test file again
- It MUST pass — show the passing output

### 3. REFACTOR — Clean up
- Improve code structure without changing behavior
- Run the full test suite (piped through `| tail -30`)
- They MUST still pass — show the output

## Fast Test Commands

Always use targeted tests during RED/GREEN. Full suite only at REFACTOR and phase boundaries.

| Language | Targeted (RED/GREEN) | Full Suite (REFACTOR) |
|----------|---------------------|-----------------------|
| Python | `uv run pytest tests/test_<module>.py -x 2>&1 \| tail -20` | `uv run pytest 2>&1 \| tail -30` |
| TypeScript | `npx vitest run <file>.test.ts 2>&1 \| tail -20` | `npm test 2>&1 \| tail -30` |
| Rust | `cargo test <module_name> 2>&1 \| tail -20` | `cargo test 2>&1 \| tail -30` |

Log full output: redirect to `.drive/test-output.log` when needed.

## When TDD Applies
- **Mandatory** during `/spec` implementation phase
- **Encouraged** in quick mode for non-trivial logic
- **Skipped** for config files, scripts, documentation, trivial changes

## Test File Conventions

| Language | Test Location | Naming |
|----------|--------------|--------|
| Python | `tests/test_<module>.py` or sibling `test_<module>.py` | `test_` prefix |
| TypeScript | `__tests__/<name>.test.ts` or sibling `<name>.test.ts` | `.test.ts` / `.spec.ts` |
| Rust | `#[cfg(test)] mod tests` in-file or `tests/` dir | `#[test]` attribute |

## The TDD Hook
The `tdd_enforcer.py` hook will remind you when source files are modified without corresponding tests. Treat these reminders seriously.
