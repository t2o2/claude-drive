#!/usr/bin/env bash
set -euo pipefail

# Show status of running Claude Drive agents.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_DIR/.drive/agents/config.json"
LOGS_DIR="$PROJECT_DIR/.drive/agents/logs"

usage() {
    echo "Usage: $(basename "$0") [-h]"
    echo ""
    echo "Show status of running Claude Drive agents."
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        -h|--help) usage ;;
    esac
done

RUNTIME=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['runtime'])" 2>/dev/null || echo "docker")

echo "=== Agent Fleet Status ==="
echo "Runtime: $RUNTIME"
echo ""

# Show running containers/workspaces
echo "--- Running Agents ---"
case "$RUNTIME" in
    docker)
        docker ps --filter "name=claude-agent-" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}" 2>/dev/null || echo "  No Docker agents running (or Docker not available)"
        ;;
    devpod)
        if command -v devpod &>/dev/null; then
            devpod list 2>/dev/null | grep -E "(claude-agent-|NAME)" || echo "  No DevPod agents running"
        else
            echo "  DevPod CLI not found"
        fi
        ;;
esac

echo ""

# Show recent logs
echo "--- Recent Agent Logs ---"
if [[ -d "$LOGS_DIR" ]]; then
    for logfile in "$LOGS_DIR"/*.log; do
        [[ -f "$logfile" ]] || continue
        agent_name=$(basename "$logfile" .log)
        echo ""
        echo "[$agent_name] (last 5 lines):"
        tail -5 "$logfile" 2>/dev/null || echo "  (empty)"
    done
    # Check for no log files
    if ! ls "$LOGS_DIR"/*.log &>/dev/null; then
        echo "  No agent logs found."
    fi
else
    echo "  Logs directory not found: $LOGS_DIR"
fi

echo ""

# Show board summary
echo "--- Board Summary ---"
if [[ -f "$PROJECT_DIR/scripts/board.py" ]]; then
    python3 "$PROJECT_DIR/scripts/board.py" list 2>/dev/null | python3 -c "
import json, sys
try:
    tasks = json.load(sys.stdin)
    counts = {}
    for t in tasks:
        s = t.get('status', 'unknown')
        counts[s] = counts.get(s, 0) + 1
    parts = [f'{v} {k}' for k, v in sorted(counts.items())]
    print('  ' + ' | '.join(parts) if parts else '  No tasks')
except:
    print('  Could not read board')
" 2>/dev/null || echo "  Board not available"
else
    echo "  board.py not found"
fi

# Show lock summary
echo ""
echo "--- Active Locks ---"
if [[ -f "$PROJECT_DIR/scripts/lock.py" ]]; then
    python3 "$PROJECT_DIR/scripts/lock.py" list 2>/dev/null | python3 -c "
import json, sys
try:
    locks = json.load(sys.stdin)
    if not locks:
        print('  No active locks')
    else:
        for l in locks:
            print(f\"  {l['task_id']} — locked by {l['agent_id']} (heartbeat: {l.get('last_heartbeat', 'N/A')})\")
except:
    print('  Could not read locks')
" 2>/dev/null || echo "  Locks not available"
else
    echo "  lock.py not found"
fi
