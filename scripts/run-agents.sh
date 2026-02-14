#!/usr/bin/env bash
set -euo pipefail

# Launch the multi-agent fleet based on .drive/agents/config.json
# Supports Docker and DevPod runtimes.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/.drive/agents/config.json"

DRY_RUN=false

usage() {
    echo "Usage: $(basename "$0") [--dry-run] [-h]"
    echo ""
    echo "Launch the multi-agent Claude Drive fleet."
    echo ""
    echo "Options:"
    echo "  --dry-run    Print commands without executing"
    echo "  -h, --help   Show this help"
    exit 0
}

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

run_cmd() {
    if $DRY_RUN; then
        echo "[DRY RUN] $*"
    else
        "$@"
    fi
}

# Parse args
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=true ;;
        -h|--help) usage ;;
        *) echo "Unknown argument: $arg"; usage ;;
    esac
done

# Validate config
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "ERROR: Config not found: $CONFIG_FILE" >&2
    exit 1
fi

# Resolve auth: prefer credentials file, fall back to env var
CLAUDE_CREDS="${HOME}/.claude/credentials.json"
AUTH_ENV_VAR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['auth']['env_var_name'])")

if [[ -f "$CLAUDE_CREDS" ]]; then
    log "Using Claude credentials from $CLAUDE_CREDS"
elif [[ -n "${!AUTH_ENV_VAR:-}" ]]; then
    log "Using $AUTH_ENV_VAR env var"
else
    echo "ERROR: No auth found. Either ~/.claude/credentials.json or $AUTH_ENV_VAR must exist." >&2
    exit 1
fi

RUNTIME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['runtime'])")
BRANCH=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['sync']['branch'])")

log "Runtime: $RUNTIME"
log "Config: $CONFIG_FILE"

# ─── Docker backend ───────────────────────────────────────────────

launch_docker() {
    local upstream_path
    upstream_path="$PROJECT_DIR/$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['sync']['upstream_path'])")"
    local image
    image=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['docker']['image'])")

    # Init bare upstream repo if needed
    if [[ ! -d "$upstream_path" ]]; then
        log "Initializing bare upstream repo at $upstream_path"
        run_cmd git init --bare "$upstream_path"
    fi

    # Push current state to upstream
    log "Pushing current state to upstream"
    if ! $DRY_RUN; then
        cd "$PROJECT_DIR"
        git remote remove _upstream 2>/dev/null || true
        git remote add _upstream "$upstream_path"
        git push _upstream "HEAD:refs/heads/$BRANCH" --force 2>/dev/null || true
        git remote remove _upstream
    fi

    # Build image from devcontainer
    log "Building Docker image: $image"
    run_cmd docker build -t "$image" -f "$PROJECT_DIR/.devcontainer/Dockerfile" "$PROJECT_DIR/.devcontainer/" 2>/dev/null \
        || run_cmd docker build -t "$image" "$PROJECT_DIR/.devcontainer/" 2>/dev/null \
        || log "WARN: No Dockerfile found, using devcontainer image directly"

    # Launch agents
    local roles_json
    roles_json=$(python3 -c "
import json
config = json.load(open('$CONFIG_FILE'))
for role in config['roles']:
    for i in range(role['count']):
        print(f\"{role['name']}|{role['name']}-{i}|{role['model']}|{role.get('max_sessions', 20)}\")
")

    while IFS='|' read -r role agent_id model max_sessions; do
        local container_name="claude-agent-${agent_id}"

        log "Launching $container_name (role=$role, model=$model, max_sessions=$max_sessions)"

        local docker_args=(
            docker run -d
            --name "$container_name"
            --rm
            -v "$upstream_path:/upstream"
            -e "AGENT_ROLE=$role"
            -e "AGENT_ID=$agent_id"
            -e "AGENT_MODEL=$model"
            -e "UPSTREAM_REMOTE=/upstream"
            -e "MAX_SESSIONS=$max_sessions"
        )

        # Mount credentials file if available, otherwise pass env var
        if [[ -f "$CLAUDE_CREDS" ]]; then
            docker_args+=(-v "$CLAUDE_CREDS:/root/.claude/credentials.json:ro")
        fi
        if [[ -n "${!AUTH_ENV_VAR:-}" ]]; then
            docker_args+=(-e "ANTHROPIC_API_KEY=${!AUTH_ENV_VAR}")
        fi

        docker_args+=("$image" bash /workspace/scripts/entrypoint.sh)
        run_cmd "${docker_args[@]}"
    done <<< "$roles_json"

    log "Docker fleet launched."
}

# ─── DevPod backend ───────────────────────────────────────────────

launch_devpod() {
    local provider
    provider=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['devpod']['provider'])")
    local upstream_remote
    upstream_remote=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['sync']['upstream_remote'])")
    local devcontainer_path="$PROJECT_DIR/.devcontainer/devcontainer.json"

    if [[ -z "$upstream_remote" ]]; then
        echo "ERROR: devpod runtime requires sync.upstream_remote to be set (e.g. git@github.com:user/repo.git)" >&2
        exit 1
    fi

    if ! command -v devpod &>/dev/null; then
        echo "ERROR: devpod CLI not found. Install from https://devpod.sh" >&2
        exit 1
    fi

    local roles_json
    roles_json=$(python3 -c "
import json
config = json.load(open('$CONFIG_FILE'))
for role in config['roles']:
    for i in range(role['count']):
        print(f\"{role['name']}|{role['name']}-{i}|{role['model']}|{role.get('max_sessions', 20)}\")
")

    while IFS='|' read -r role agent_id model max_sessions; do
        local workspace_name="claude-agent-${agent_id}"

        log "Provisioning DevPod workspace: $workspace_name (provider=$provider, role=$role)"
        run_cmd devpod up "$PROJECT_DIR" \
            --provider "$provider" \
            --workspace-id "$workspace_name" \
            --devcontainer-path "$devcontainer_path" \
            --ide none

        log "Starting entrypoint in $workspace_name"
        run_cmd devpod ssh "$workspace_name" -- \
            "ANTHROPIC_API_KEY='${!AUTH_ENV_VAR}' \
             AGENT_ROLE='$role' \
             AGENT_ID='$agent_id' \
             AGENT_MODEL='$model' \
             UPSTREAM_REMOTE='$upstream_remote' \
             MAX_SESSIONS='$max_sessions' \
             nohup bash /workspace/scripts/entrypoint.sh > /tmp/agent.log 2>&1 &"
    done <<< "$roles_json"

    log "DevPod fleet launched."
}

# ─── Dispatch ─────────────────────────────────────────────────────

case "$RUNTIME" in
    docker) launch_docker ;;
    devpod) launch_devpod ;;
    *) echo "ERROR: Unknown runtime: $RUNTIME" >&2; exit 1 ;;
esac
