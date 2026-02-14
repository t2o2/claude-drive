#!/usr/bin/env bash
set -euo pipefail

# Stop all running Claude Drive agents.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/.drive/agents/config.json"

usage() {
    echo "Usage: $(basename "$0") [-h]"
    echo ""
    echo "Stop all running Claude Drive agents."
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) usage ;;
    esac
done

log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }

RUNTIME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['runtime'])" 2>/dev/null || echo "docker")

case "$RUNTIME" in
    docker)
        containers=$(docker ps --filter "name=claude-agent-" --format "{{.Names}}" 2>/dev/null || true)
        if [[ -z "$containers" ]]; then
            log "No running agent containers found."
            exit 0
        fi
        log "Stopping containers:"
        echo "$containers" | while read -r name; do
            log "  Stopping $name"
            docker stop "$name" 2>/dev/null || true
        done
        log "All agents stopped."
        ;;
    devpod)
        if ! command -v devpod &>/dev/null; then
            echo "ERROR: devpod CLI not found" >&2
            exit 1
        fi
        workspaces=$(devpod list 2>/dev/null | grep "claude-agent-" | awk '{print $1}' || true)
        if [[ -z "$workspaces" ]]; then
            log "No running DevPod agent workspaces found."
            exit 0
        fi
        log "Stopping DevPod workspaces:"
        echo "$workspaces" | while read -r name; do
            log "  Stopping $name"
            devpod stop "$name" 2>/dev/null || true
        done
        log "All agents stopped."
        ;;
    *)
        echo "ERROR: Unknown runtime: $RUNTIME" >&2
        exit 1
        ;;
esac
