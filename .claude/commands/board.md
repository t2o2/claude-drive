---
description: "View and manage the multi-agent task board"
user-invocable: true
---

# /board — Agent Task Board

You are the `/board` command. Provide a human interface to the multi-agent task board.

## Behavior

### No arguments — show board overview

1. Read all tasks from `.drive/agents/tasks/` using `python3 scripts/board.py list`
2. Read all locks from `python3 scripts/lock.py list`
3. Read agent config from `.drive/agents/config.json`
4. Display summary:

```
Agent Task Board
================
Tasks: 3 open | 2 locked | 5 done | 1 failed

Locked:
  #abc123 "Fix auth bug" — locked by implementer-0 (heartbeat: 2m ago)
  #def456 "Add logging" — locked by implementer-1 (heartbeat: 5m ago)

Open (by priority):
  #ghi789 [P1] "Fix SQL injection in search"
  #jkl012 [P2] "Add dark mode toggle"
  #mno345 [P3] "Update API docs"
```

5. Detect runtime from config and show agent status:
   - Docker: run `docker ps --filter name=claude-agent --format "table {{.Names}}\t{{.Status}}"`
   - DevPod: run `devpod list 2>/dev/null | grep claude-agent`

6. Ask what to do using `AskUserQuestion`:

### Actions

**Add task:**
- Ask for description and priority (1=high, 2=medium, 3=low)
- Run: `python3 scripts/board.py add "<description>" --priority <N>`

**View messages:**
- Run: `python3 scripts/board.py messages <role>` for each role
- Show messages grouped by recipient role
- Offer to mark messages as read

**Tail agent logs:**
- List available log files in `.drive/agents/logs/`
- Ask which agent's log to view
- Show last 30 lines of the selected log

**Force-release lock:**
- Show locked tasks with their owners
- Ask which lock to release — **require explicit confirmation**
- Run: `python3 scripts/lock.py release <task_id> <agent_id>`
- Note: only use this for stuck/crashed agents

**Poll Telegram:**
- If Telegram is configured in `.drive/config.json`, poll for new messages
- Add each message as a new task on the board:
  `python3 scripts/board.py add "<telegram message>" --priority 2`

**Cleanup:**
- Archive completed tasks older than 7 days
- Clean stale locks (older than 2 hours)
- Run: `python3 scripts/lock.py cleanup`

## Important
- All board/lock operations go through the CLI wrappers in `scripts/`
- Force-releasing locks can cause duplicate work — always confirm
- Agent status detection adapts to runtime (docker vs devpod) from config
