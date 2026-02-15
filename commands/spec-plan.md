---
description: "Phase 1: Create and refine a spec plan"
user-invocable: false
model: opus
---

# Spec Plan Phase

You are in the **planning phase** of spec-driven development.

## Input
- If argument is a description: create a new plan
- If argument is `--continue <path>`: resume editing an existing plan

## Steps

### 1. Explore
- Read relevant source files to understand the codebase
- Identify affected modules, dependencies, and integration points
- Note existing patterns and conventions

### 2. Design
- Break the work into discrete, testable tasks
- Define dependencies between tasks (what blocks what)
- Write a clear Definition of Done (DoD) for each task
- Identify architecture decisions and their rationale
- List risks and mitigations

### 3. Write Plan File
Create `docs/plans/YYYY-MM-DD-<slug>.json` with this schema:

```json
{
  "title": "<Title>",
  "status": "PENDING",
  "created": "YYYY-MM-DD",
  "description": "<What we're building and why>",
  "tasks": [
    {
      "id": 1,
      "name": "<task name>",
      "description": "<what to implement>",
      "dependencies": [],
      "dod": "<measurable definition of done>",
      "files": ["<expected files to create/modify>"],
      "passes": false
    },
    {
      "id": 2,
      "name": "<task name>",
      "description": "<what to implement>",
      "dependencies": [1],
      "dod": "<measurable definition of done>",
      "files": ["<expected files to create/modify>"],
      "passes": false
    }
  ],
  "architecture_decisions": [
    {"decision": "<what>", "rationale": "<why>"}
  ],
  "risks": [
    {"risk": "<what could go wrong>", "mitigation": "<how to handle>"}
  ]
}
```

### 4. Validate
Launch two review agents **in parallel** using the Task tool:
- `plan-verifier` agent: checks completeness and validity
- `plan-challenger` agent: adversarial review for blind spots

### 5. Incorporate Feedback
- Address critical issues from both agents
- Update the plan file

### 6. Present for Approval
- Show the final plan to the user
- Ask for explicit approval
- When approved, update `status` to `"APPROVED"`

## Rules
- Do NOT start implementation in this phase
- The only stopping point is user approval
- Keep tasks atomic — each should be completable in one TDD cycle
- Output valid JSON — use `json.dumps` with `indent=2` when writing plan files
