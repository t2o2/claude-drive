---
description: "View and manage Telegram comments/tasks"
user-invocable: true
---

# /comment — Telegram Comments & Tasks

You are the `/comment` command. Show pending tasks from Telegram and let the user manage them.

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
   - "Manage pairing" — show pairing info and management options (see below)

6. After any action, save updated config back to `.drive/config.json`

## Manage Pairing

When the user selects "Manage pairing":

1. Show current pairing info:
   ```
   Pairing code: 482916
   Approved senders: [123456789, 987654321]  (or "none" if empty)
   ```

2. Ask the user what to do using `AskUserQuestion`:
   - "Regenerate code" — generate a new 6-digit random code, save to `telegram.pairing_code`, display: "New pairing code: **<code>**. Send this to your bot."
   - "Revoke sender" — ask which sender ID to remove from `telegram.approved_senders`
   - "Back" — return to the main feedback menu

## Important
- Always show the task text, source, and timestamp
- When marking done, set `done: true` — do not delete the task (preserves history)
- When dismissing, remove the task entirely from the array
- Poll uses the same logic as `session_start.py` — respect `chat_id` filtering, `approved_senders`, and update `last_update_id`
- Pairing code must be a 6-digit integer (100000–999999)
