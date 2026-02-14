---
description: "First-run project setup — configure Claude Drive for this project"
user-invocable: true
---

# /setup — Project Setup

You are the `/setup` command. Walk the user through first-time project configuration.

## Behavior

1. Check if `.drive/config.json` already exists
   - If yes: show current config and ask if they want to reconfigure
   - If no: proceed with interview

2. Ask the user these questions using `AskUserQuestion` (all in one call):

   **Question 1: Project name and description**
   - Ask: "What's the project name and a brief one-line description?"
   - Free text (use "Other" option pattern — provide sensible defaults based on directory name)

   **Question 2: Primary language**
   - Options: Python, TypeScript, Rust, Other
   - Auto-detect from project files if possible (pyproject.toml → Python, package.json → TypeScript, Cargo.toml → Rust)

   **Question 3: TDD strictness**
   - Options:
     - "Strict" — always require tests before source changes
     - "Relaxed" — encourage tests for non-trivial logic, skip for config/scripts

   **Question 4: Enable Telegram notifications?**
   - Options: Yes, No
   - If Yes: follow up asking for bot token and chat ID

3. Save answers to `.drive/config.json`:

```json
{
  "project_name": "...",
  "project_description": "...",
  "language": "python",
  "tdd_strictness": "strict",
  "telegram": {
    "enabled": false,
    "bot_token": "",
    "chat_id": "",
    "last_update_id": 0
  },
  "tasks": []
}
```

4. Confirm setup is complete and summarize the saved config.

## Important
- Create `.drive/` directory if it doesn't exist
- Use `Write` tool to save the JSON config
- If Telegram is enabled, validate that both bot_token and chat_id are non-empty
- Keep the conversation friendly but efficient — this should take under a minute
