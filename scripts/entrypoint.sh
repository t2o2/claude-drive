#!/usr/bin/env bash
set -euo pipefail

# --- Logging ---

log() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"
}

log_error() {
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] ERROR: $*" >&2
}

# --- EXIT trap: crash logging ---

on_exit() {
  local exit_code=$?
  if [ "$exit_code" -ne 0 ]; then
    local crash_log="${BOARD_DIR:-/board}/logs/${AGENT_ID}-crash.log"
    mkdir -p "$(dirname "$crash_log")"
    {
      echo "---"
      echo "timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo "exit_code: $exit_code"
      echo "session_count: ${SESSION_COUNT:-0}"
      echo "idle_count: ${IDLE_COUNT:-0}"
      echo "last_command: ${BASH_COMMAND:-unknown}"
    } >> "$crash_log"
    log_error "Agent ${AGENT_ID} crashed with exit code ${exit_code}. See ${crash_log}"
  fi
}

trap on_exit EXIT

# --- Step 1: Validate required env vars ---

validate_env() {
  local missing=0

  if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ] && [ ! -f "${HOME}/.claude/credentials.json" ]; then
    log_error "No auth found: set ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, or mount ~/.claude/credentials.json"
    missing=1
  fi

  if [ -z "${AGENT_ROLE:-}" ]; then
    log_error "AGENT_ROLE is required but not set"
    missing=1
  fi

  if [ -z "${AGENT_ID:-}" ]; then
    log_error "AGENT_ID is required but not set"
    missing=1
  fi

  if [ "$missing" -eq 1 ]; then
    log_error "Missing required environment variables. Exiting."
    exit 1
  fi

  AGENT_MODEL="${AGENT_MODEL:-claude-sonnet-4-5-20250929}"
  UPSTREAM_REMOTE="${UPSTREAM_REMOTE:-/upstream}"
  MAX_SESSIONS="${MAX_SESSIONS:-20}"
  AGENT_BRANCH="agent/${AGENT_ID}"

  # Use /board/ mount if available, otherwise fall back to workspace-local dirs
  if [ -d "/board/tasks" ]; then
    BOARD_DIR="/board"
  else
    BOARD_DIR=".drive/agents"
  fi
  export BOARD_DIR

  log "Agent ${AGENT_ID} starting with role=${AGENT_ROLE} model=${AGENT_MODEL}"
  log "Upstream remote: ${UPSTREAM_REMOTE}"
  log "Agent branch: ${AGENT_BRANCH}"
  log "Max sessions: ${MAX_SESSIONS}"
  log "Board dir: ${BOARD_DIR}"
}

# --- Step 2: Clone from upstream and create agent branch ---

clone_upstream() {
  if [ -d "/workspace/.git" ]; then
    log "Workspace already contains a git repo, skipping clone"
    cd /workspace
  elif [ "$(ls -A /workspace 2>/dev/null)" ]; then
    log "Workspace is non-empty but not a git repo, attempting to use as-is"
    cd /workspace
  else
    log "Cloning from upstream: ${UPSTREAM_REMOTE}"
    if git clone "${UPSTREAM_REMOTE}" /workspace; then
      log "Clone successful"
      cd /workspace
    else
      log_error "Failed to clone from ${UPSTREAM_REMOTE}"
      exit 1
    fi
  fi

  # Create or checkout agent branch from main
  if git show-ref --verify --quiet "refs/heads/${AGENT_BRANCH}" 2>/dev/null; then
    git checkout "${AGENT_BRANCH}"
    log "Checked out existing branch ${AGENT_BRANCH}"
  else
    git checkout -b "${AGENT_BRANCH}"
    log "Created new branch ${AGENT_BRANCH}"
  fi

  # Pull latest main into agent branch so we start from current state
  git pull "${UPSTREAM_REMOTE}" main --rebase 2>/dev/null || {
    git rebase --abort 2>/dev/null || true
    git pull "${UPSTREAM_REMOTE}" main --no-rebase 2>/dev/null || true
  }
  log "Agent branch ${AGENT_BRANCH} is up to date with main"
}

# --- Step 3: Health check ---

health_check() {
  log "Running health check..."

  if ! command -v claude &>/dev/null; then
    log_error "claude CLI not found in PATH"
    exit 1
  fi

  local version
  version=$(claude --version 2>&1) || true
  log "Claude CLI version: ${version}"

  if ! command -v git &>/dev/null; then
    log_error "git not found in PATH"
    exit 1
  fi

  log "Health check passed"
}

# --- Step 4: Push agent branch ---

push_branch() {
  local max_retries=3
  local attempt=0

  while [ "$attempt" -lt "$max_retries" ]; do
    attempt=$((attempt + 1))
    log "Push attempt ${attempt}/${max_retries}"

    if git push "${UPSTREAM_REMOTE}" "${AGENT_BRANCH}:refs/heads/${AGENT_BRANCH}" --force-with-lease 2>/dev/null; then
      log "Push to ${AGENT_BRANCH} succeeded"
      return 0
    else
      log "Push failed on attempt ${attempt}"
      sleep 2
    fi
  done

  # Fallback: force push (agent owns this branch exclusively)
  if git push "${UPSTREAM_REMOTE}" "${AGENT_BRANCH}:refs/heads/${AGENT_BRANCH}" --force 2>/dev/null; then
    log "Force push to ${AGENT_BRANCH} succeeded"
    return 0
  fi

  log_error "Failed to push after ${max_retries} attempts"
  return 1
}

# --- Step 5: Run a Claude session ---

run_session() {
  local role_file=".drive/agents/roles/${AGENT_ROLE}.md"

  if [ ! -f "$role_file" ]; then
    log_error "Role file not found: ${role_file}"
    return 1
  fi

  local prompt
  prompt=$(cat "$role_file")

  # Replace board.py references in prompt with full path + correct --tasks-dir
  prompt="${prompt//python3 scripts\/board.py/python3 scripts\/board.py --tasks-dir ${BOARD_DIR}\/tasks\/ --messages-dir ${BOARD_DIR}\/messages\/}"
  # Also replace lock.py references with full path
  prompt="${prompt//python3 scripts\/lock.py/python3 scripts\/lock.py --locks-dir ${BOARD_DIR}\/locks\/}"

  # Inject board + branch + identity context at the top
  local context="YOUR AGENT_ID is: ${AGENT_ID}
Use '${AGENT_ID}' (not \$AGENT_ID) in all commands and commit messages.

IMPORTANT: The task board is mounted at ${BOARD_DIR}/.
All board.py commands MUST include: --tasks-dir ${BOARD_DIR}/tasks/ --messages-dir ${BOARD_DIR}/messages/
All lock.py commands MUST include: --locks-dir ${BOARD_DIR}/locks/
Example: python3 scripts/board.py --tasks-dir ${BOARD_DIR}/tasks/ list --status open

GIT BRANCH: You are working on branch '${AGENT_BRANCH}'.
Do NOT push to main. Commit to your current branch. The entrypoint handles pushing.
Do NOT run git push — the entrypoint will push your branch after the session."

  log "Starting Claude session ${SESSION_COUNT} with role ${AGENT_ROLE}"

  claude --dangerously-skip-permissions \
    -p "${context}

${prompt}" \
    --model "$AGENT_MODEL" \
    2>&1 | tee -a "$LOG_FILE"

  log "Claude session ${SESSION_COUNT} completed"
}

# --- Step 6: Check for changes and commit ---

commit_changes() {
  local status
  status=$(git status --porcelain 2>/dev/null)

  if [ -z "$status" ]; then
    log "No uncommitted changes after session ${SESSION_COUNT}"
    return 1
  fi

  log "Uncommitted changes detected, committing..."
  git add -A
  git commit -m "agent/${AGENT_ID}: session ${SESSION_COUNT}" --no-verify
  log "Committed changes for session ${SESSION_COUNT}"
  return 0
}

# --- Main ---

main() {
  validate_env
  clone_upstream
  health_check

  # Ralph-loop variables
  SESSION_COUNT=0
  IDLE_COUNT=0
  MAX_IDLE=5
  LOG_FILE="${BOARD_DIR}/logs/${AGENT_ID}.log"
  mkdir -p "$(dirname "$LOG_FILE")"

  log "Entering Ralph-loop (max_sessions=${MAX_SESSIONS}, max_idle=${MAX_IDLE})"

  while true; do
    log "--- Session ${SESSION_COUNT} ---"

    # Rebase agent branch on latest main before each session
    git fetch "${UPSTREAM_REMOTE}" main 2>/dev/null || true
    git rebase "${UPSTREAM_REMOTE}/main" 2>/dev/null || {
      git rebase --abort 2>/dev/null || true
      log "Rebase on main failed, continuing on current state"
    }

    # Run Claude session
    if ! run_session; then
      log_error "Session ${SESSION_COUNT} failed to start"
      IDLE_COUNT=$((IDLE_COUNT + 1))
      if [ "$IDLE_COUNT" -ge "$MAX_IDLE" ]; then
        log "Reached max idle count (${MAX_IDLE}), exiting"
        exit 0
      fi
      sleep 10
      continue
    fi

    # Commit any uncommitted changes (safety net — agent should commit in-session)
    commit_changes || true

    # Check if there are commits to push
    local_head=$(git rev-parse HEAD 2>/dev/null)
    remote_head=$(git rev-parse "${UPSTREAM_REMOTE}/main" 2>/dev/null || echo "none")

    if [ "$local_head" != "$remote_head" ]; then
      IDLE_COUNT=0
      log "Unpushed commits on ${AGENT_BRANCH}, pushing..."
      if ! push_branch; then
        log_error "Failed to push ${AGENT_BRANCH}"
      fi
    else
      IDLE_COUNT=$((IDLE_COUNT + 1))
      log "No new commits after session. Idle count: ${IDLE_COUNT}/${MAX_IDLE}"

      if [ "$IDLE_COUNT" -ge "$MAX_IDLE" ]; then
        log "Reached max idle count (${MAX_IDLE}), exiting gracefully"
        exit 0
      fi
    fi

    # Increment session counter
    SESSION_COUNT=$((SESSION_COUNT + 1))

    if [ "$SESSION_COUNT" -ge "$MAX_SESSIONS" ]; then
      log "Reached max sessions (${MAX_SESSIONS}), exiting"
      exit 0
    fi

    log "Sleeping 10s before next session..."
    sleep 10
  done
}

main "$@"
