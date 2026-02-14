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
  .claude/CLAUDE.md
  .claude/settings.json
  .claude/hooks/session_start.py
  .claude/hooks/file_checker.py
  .claude/hooks/context_monitor.py
  .claude/hooks/tdd_enforcer.py
  .claude/commands/spec.md
  .claude/commands/spec-plan.md
  .claude/commands/spec-implement.md
  .claude/commands/spec-verify.md
  .claude/agents/plan-verifier.md
  .claude/agents/plan-challenger.md
  .claude/agents/spec-reviewer-compliance.md
  .claude/agents/spec-reviewer-quality.md
  .claude/rules/coding-standards.md
  .claude/rules/context-continuation.md
  .claude/rules/tdd-enforcement.md
  .claude/rules/verification-before-completion.md
  .claude/rules/workflow-enforcement.md
  .claude/rules/python-rules.md
  .claude/rules/typescript-rules.md
  .claude/rules/rust-rules.md
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

# Make hooks executable
chmod +x .claude/hooks/*.py 2>/dev/null || true

# --- Create runtime directories ---

mkdir -p .drive/sessions
mkdir -p docs/plans
info ".drive/ runtime directory created"
info "docs/plans/ plan directory created"

# --- Update .gitignore ---

if [ -f ".gitignore" ]; then
  if ! grep -qxF ".drive/" .gitignore 2>/dev/null; then
    printf "\n.drive/\n" >> .gitignore
    info "Added .drive/ to existing .gitignore"
  else
    info ".drive/ already in .gitignore"
  fi
else
  printf ".drive/\n" > .gitignore
  info "Created .gitignore with .drive/"
fi

# --- Done ---

printf "\n${BOLD}${GREEN}Claude Drive installed!${RESET}\n\n"
printf "  Start a Claude Code session to activate the framework.\n"
printf "  Edit ${BOLD}.claude/CLAUDE.md${RESET} to customize for your project.\n\n"
printf "  Optional cleanup — remove unused language rules:\n"
printf "    rm .claude/rules/python-rules.md\n"
printf "    rm .claude/rules/typescript-rules.md\n"
printf "    rm .claude/rules/rust-rules.md\n\n"
