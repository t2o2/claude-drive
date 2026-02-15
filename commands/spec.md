---
description: "Spec-driven development workflow: plan → implement → verify"
argument-hint: "<description> or <plan-file.json> or --continue <plan-file.json>"
user-invocable: true
---

# /spec — Spec-Driven Development

You are the `/spec` dispatcher. Route to the appropriate phase based on arguments.

## Routing Logic

### No arguments
1. List all plan files in `docs/plans/` (both `.json` and legacy `.md`) with their Status
2. Ask the user what they'd like to do:
   - Create a new spec
   - Continue an existing one
   - Review a completed one

### Argument is a description (not a file path)
- This is a new spec request
- Invoke the `spec-plan` command with the description as argument:
  `Use Skill('spec-plan', args='<the description>')`

### Argument is a file path or `--continue <path>`
1. Read the plan file (JSON format: parse with `json.loads`)
2. Check the `status` field
3. Route based on status:

| Status | Action |
|--------|--------|
| `PENDING` (no approval note) | Resume planning: `Skill('spec-plan', args='--continue <path>')` |
| `APPROVED` or `PENDING` with approval | Start implementation: `Skill('spec-implement', args='<path>')` |
| `COMPLETE` | Start verification: `Skill('spec-verify', args='<path>')` |
| `VERIFIED` | Inform user the spec is done. Ask if they want to review or modify. |

## Important
- Always read the plan file before routing to confirm actual status
- If the plan file doesn't exist, treat the argument as a new spec description
- Plan files are JSON — parse them, don't regex them
