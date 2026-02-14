---
globs: "*"
---

# Workflow Enforcement

## Task Tracking
- Use `TaskCreate`/`TaskUpdate` for any work requiring 3+ steps
- Mark tasks `in_progress` before starting, `completed` when done
- Include clear descriptions and activeForm text

## Complexity Triage
Before starting work, assess complexity:

| Complexity | Criteria | Action |
|-----------|----------|--------|
| **Simple** | 1-2 files, clear fix | Execute directly |
| **Medium** | 3-4 files, well-defined | Use TaskCreate for tracking |
| **Complex** | 5+ files, new patterns, architecture | Suggest `/spec` |

## Context Guard
Before major phase transitions (e.g., plan → implement, implement → verify):
1. Confirm all prior phase deliverables are complete
2. Run relevant checks (tests, lints)
3. Update plan file status if in spec mode

## Progress Updates
- Update plan file checkboxes as tasks complete
- Show actual command output, not summaries
- If blocked, explain why and propose alternatives
