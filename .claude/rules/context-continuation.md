---
globs: "*"
---

# Context Continuation Protocol

## On Session Start
1. Check if `.drive/sessions/continuation.md` exists
2. If yes: read it, announce "Resuming from continuation file", follow the Next Steps
3. Delete the continuation file after reading

## During Work
When the context monitor hook warns about high context usage:
- **~75% warning:** Start wrapping up current subtask. Avoid starting new large operations.
- **~88% critical:** Immediately:
  1. Append a progress block to `.drive/claude-progress.txt`
  2. Write `.drive/sessions/continuation.md` with full state:
     - Current task and phase
     - What's been completed (with file paths)
     - What remains (ordered next steps)
     - Key decisions made
     - Any open questions or blockers

## Continuation File Location
Always use `.drive/sessions/continuation.md` — this path is hardcoded in the session_start hook.

## Key Principle
The next session should be able to resume seamlessly without the user re-explaining anything.
