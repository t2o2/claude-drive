---
description: "Phase 2: TDD implementation of an approved plan"
user-invocable: false
model: opus
---

# Spec Implementation Phase

You are in the **implementation phase** of spec-driven development.

## Input
- Path to an APPROVED plan file (JSON) in `docs/plans/`

## Process

### For each task where `passes` is `false` (in dependency order):

#### 1. RED — Write failing test
- Create or update test file following project conventions
- Write test(s) that describe the expected behavior from the `dod`
- Run ONLY the targeted test file: e.g., `uv run pytest tests/test_<module>.py -x 2>&1 | tail -20`
- It MUST fail — show the failing output

#### 2. GREEN — Write minimal implementation
- Write the minimum code to make the test pass
- Run ONLY the targeted test file again
- It MUST pass — show the passing output

#### 3. REFACTOR — Clean up
- Improve code structure, naming, duplication
- Run full test suite: e.g., `uv run pytest 2>&1 | tail -30`
- They MUST still pass — show the output
- Run linter — fix any warnings

#### 4. Completion Evidence Gate
Before marking a task as passing, you MUST:
1. Paste the EXACT test command and its output (minimum 3 lines)
2. Output must contain a recognizable pass indicator (e.g., "passed", "test result: ok", "Tests: X passed")
3. If any test fails, fix it before proceeding — do not mark `passes: true`

#### 5. Update Plan
- Read the current JSON plan file
- Set the completed task's `passes` field to `true`
- Write the updated JSON back (preserve all other fields exactly)
- Do NOT modify `name`, `description`, or `dod` fields

### After all tasks complete:
1. Run full test suite and show output (pipe through `| tail -30`)
2. Run type checker and show output
3. Run linter and show output
4. All three must pass — paste exact output as evidence
5. Update plan `status` to `"COMPLETE"`

## Rules
- Follow dependency order strictly — never start a task whose dependencies have `passes: false`
- Every source file change must have a corresponding test change
- Show actual command output at each step, never summarize
- Use targeted tests during RED/GREEN, full suite only at REFACTOR and phase boundaries
- If a test fails unexpectedly, debug it before proceeding
- If you discover the plan needs changes, note them but don't modify the plan structure without user approval
- Maximum 3 full test suite runs per session — use targeted tests otherwise
