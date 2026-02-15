---
description: "Phase 3: Dual-agent verification of completed implementation"
user-invocable: false
model: opus
---

# Spec Verification Phase

You are in the **verification phase** of spec-driven development.

## Input
- Path to a COMPLETE plan file (JSON) in `docs/plans/`

## Process

### 1. Read Plan
Parse the JSON plan file. Verify:
- `status` is `"COMPLETE"`
- All tasks have `passes: true`
- If any task has `passes: false`, route back to implementation phase

### 2. Launch Dual Review
Launch two review agents **in parallel** using the Task tool:
- `spec-reviewer-compliance` agent: verifies implementation matches plan
- `spec-reviewer-quality` agent: reviews code quality, security, testing

### 3. Run Full Verification Suite
Run all verification commands and capture output:
- Full test suite
- Type checking
- Linting / formatting check

### 4. Triage Findings
Categorize all findings from agents and verification:

| Severity | Criteria | Action |
|----------|----------|--------|
| **must_fix** | Broken tests, type errors, security issues, plan non-compliance | Fix immediately |
| **should_fix** | Code smells, missing edge case tests, style issues | Fix in this phase |
| **optional** | Suggestions, minor improvements | Note but skip |

### 5. Fix Issues
- Address all `must_fix` items
- Address all `should_fix` items
- Run verification suite again after fixes
- Maximum 3 fix-verify iterations

### 6. Final Report
Present summary:
- All checks passing (with output)
- Compliance status
- Quality findings addressed
- Any remaining `optional` items noted

### 7. Update Status
- Update plan `status` to `"VERIFIED"`

## Rules
- Never skip the dual-agent review
- Show actual verification output, not summaries
- If must_fix items remain after 3 iterations, stop and report to user
- The plan is only VERIFIED when all must_fix and should_fix items are resolved
