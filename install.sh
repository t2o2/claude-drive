#!/usr/bin/env bash
set -euo pipefail

# Claude Drive — Framework for long-running Claude Code sessions
# Install: curl -fsSL https://raw.githubusercontent.com/t2o2/claude-drive/main/install.sh | bash

REPO="t2o2/claude-drive"
BRANCH="main"
BASE_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}"

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { printf "${GREEN}✓${RESET} %s\n" "$1"; }
warn()  { printf "${YELLOW}!${RESET} %s\n" "$1"; }
error() { printf "${RED}✗${RESET} %s\n" "$1"; exit 1; }

# --- Preflight checks ---

command -v curl >/dev/null 2>&1 || error "curl is required but not installed"

if [ ! -d ".git" ] && [ -z "${FORCE:-}" ]; then
  error "Not a git repository. Run from your project root or set FORCE=1 to skip this check."
fi

if [ -d ".claude" ] && [ -z "${FORCE:-}" ]; then
  error ".claude/ already exists. Set FORCE=1 to overwrite."
fi

printf "\n${BOLD}Installing Claude Drive framework...${RESET}\n\n"

# --- File manifest ---
# Each line: <local_path>
FILES=(
  # Core config
  .claude/CLAUDE.md
  .claude/settings.json

  # Hooks
  .claude/hooks/session_start.py
  .claude/hooks/session_end.py
  .claude/hooks/agent_session_start.py
  .claude/hooks/file_checker.py
  .claude/hooks/context_monitor.py
  .claude/hooks/tdd_enforcer.py

  # Commands
  .claude/commands/setup.md
  .claude/commands/comment.md
  .claude/commands/board.md
  .claude/commands/spec.md
  .claude/commands/spec-plan.md
  .claude/commands/spec-implement.md
  .claude/commands/spec-verify.md

  # Spec agents
  .claude/agents/plan-verifier.md
  .claude/agents/plan-challenger.md
  .claude/agents/spec-reviewer-compliance.md
  .claude/agents/spec-reviewer-quality.md

  # Rules
  .claude/rules/coding-standards.md
  .claude/rules/context-continuation.md
  .claude/rules/tdd-enforcement.md
  .claude/rules/verification-before-completion.md
  .claude/rules/workflow-enforcement.md
  .claude/rules/python-rules.md
  .claude/rules/typescript-rules.md
  .claude/rules/rust-rules.md

  # Multi-agent: devcontainer
  .devcontainer/Dockerfile
  .devcontainer/devcontainer.json

  # Multi-agent: role prompts
  .drive/agents/config.json
  .drive/agents/roles/implementer.md
  .drive/agents/roles/reviewer.md
  .drive/agents/roles/docs.md
  .drive/agents/roles/janitor.md

  # Multi-agent: scripts
  scripts/board.py
  scripts/lock.py
  scripts/validate_agent_config.py
  scripts/run-agents.sh
  scripts/stop-agents.sh
  scripts/agent-status.sh
  scripts/entrypoint.sh
  scripts/smoke-test.sh
  scripts/orchestrator.py
  scripts/dashboard.py
  scripts/templates/dashboard.html
)

# --- Download files ---

for file in "${FILES[@]}"; do
  dir=$(dirname "$file")
  mkdir -p "$dir"
  if curl -fsSL "${BASE_URL}/${file}" -o "$file"; then
    info "$file"
  else
    warn "Failed to download $file (skipped)"
  fi
done

# Make hooks and scripts executable
chmod +x .claude/hooks/*.py 2>/dev/null || true
chmod +x scripts/*.sh 2>/dev/null || true

# --- Create runtime directories ---

mkdir -p .drive/sessions
mkdir -p .drive/agents/tasks
mkdir -p .drive/agents/locks
mkdir -p .drive/agents/logs
mkdir -p .drive/agents/messages
mkdir -p docs/plans
info ".drive/ runtime directories created"
info "docs/plans/ plan directory created"

# --- Update .gitignore ---

GITIGNORE_ENTRIES=(
  ".drive/config.json"
  ".drive/claude-progress.txt"
  ".drive/sessions/"
  ".drive/upstream/"
  ".drive/test-output.log"
  ".drive/lint-output.log"
  ".drive/agents/tasks/"
  ".drive/agents/locks/"
  ".drive/agents/logs/"
  ".drive/agents/messages/"
  ".drive/agents/board-meta.json"
  "__pycache__/"
)

if [ ! -f ".gitignore" ]; then
  touch .gitignore
fi

# Remove legacy blanket .drive/ ignore if present
if grep -qxF ".drive/" .gitignore 2>/dev/null; then
  sed -i.bak '/^\.drive\/$/d' .gitignore && rm -f .gitignore.bak
  info "Removed legacy blanket .drive/ from .gitignore"
fi

added=0
for entry in "${GITIGNORE_ENTRIES[@]}"; do
  if ! grep -qxF "$entry" .gitignore 2>/dev/null; then
    echo "$entry" >> .gitignore
    added=$((added + 1))
  fi
done
if [ "$added" -gt 0 ]; then
  info "Added $added entries to .gitignore"
else
  info ".gitignore already up to date"
fi

# --- Done ---

printf "\n${BOLD}${GREEN}Claude Drive installed!${RESET}\n\n"
printf "  Start a Claude Code session to activate the framework.\n"
printf "  Edit ${BOLD}.claude/CLAUDE.md${RESET} to customize for your project.\n\n"
printf "  Optional cleanup — remove unused language rules:\n"
printf "    rm .claude/rules/python-rules.md\n"
printf "    rm .claude/rules/typescript-rules.md\n"
printf "    rm .claude/rules/rust-rules.md\n\n"
printf "  Multi-agent mode:\n"
printf "    Edit ${BOLD}.drive/agents/config.json${RESET} to configure the fleet.\n"
printf "    Run ${BOLD}scripts/run-agents.sh${RESET} to launch agents.\n\n"
