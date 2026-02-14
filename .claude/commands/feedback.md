---
description: "View and manage Telegram feedback tasks"
user-invocable: true
---

# /feedback — Telegram Feedback Tasks

You are the `/feedback` command. Show pending tasks from Telegram and let the user manage them.

## Behavior

1. Read `tasks` from `.drive/config.json`
2. Filter to pending tasks (where `done` is `false`)
3. If no pending tasks, say "No pending feedback tasks." and offer to poll Telegram now
4. If pending tasks exist, list them numbered:

```
Pending feedback tasks:
1. Fix the login bug (from telegram, 2026-02-14T10:30:00Z)
2. Add dark mode toggle (from telegram, 2026-02-14T11:00:00Z)
```

5. Ask the user what to do using `AskUserQuestion`:

   **Options:**
   - "Work on a task" — ask which number, then start working on it
   - "Mark done" — ask which number(s), set `done: true` in config
   - "Dismiss" — ask which number(s), remove from tasks array
   - "Poll now" — call `curl -s "https://api.telegram.org/bot<token>/getUpdates?offset=<last_update_id+1>"`, parse new messages, add to tasks, update `last_update_id`

6. After any action, save updated config back to `.drive/config.json`

## Important
- Always show the task text, source, and timestamp
- When marking done, set `done: true` — do not delete the task (preserves history)
- When dismissing, remove the task entirely from the array
- Poll uses the same logic as `session_start.py` — respect `chat_id` filtering and update `last_update_id`
