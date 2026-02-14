#!/usr/bin/env bash
# Smoke tests for Docker and DevPod backends.
# Usage: ./scripts/smoke-test.sh [--docker-only | --devpod-only | -h]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEVCONTAINER_DIR="$PROJECT_ROOT/.devcontainer"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

RUN_DOCKER=true
RUN_DEVPOD=true

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Smoke tests for Docker and DevPod backends.

Options:
  --docker-only   Run only the Docker smoke test
  --devpod-only   Run only the DevPod smoke test
  -h, --help      Show this help message
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --docker-only)  RUN_DOCKER=true; RUN_DEVPOD=false; shift ;;
        --devpod-only)  RUN_DOCKER=false; RUN_DEVPOD=true; shift ;;
        -h|--help)      usage ;;
        *)              log_error "Unknown option: $1"; usage ;;
    esac
done

# ── Docker smoke test ─────────────────────────────────────

docker_smoke_test() {
    log_info "=== Docker Smoke Test ==="

    if ! command -v docker &>/dev/null; then
        log_error "Docker is not installed or not in PATH. Skipping Docker test."
        return 1
    fi

    if ! docker info &>/dev/null; then
        log_error "Docker daemon is not running. Skipping Docker test."
        return 1
    fi

    if [[ ! -f "$DEVCONTAINER_DIR/devcontainer.json" ]]; then
        log_error "No devcontainer.json found at $DEVCONTAINER_DIR"
        return 1
    fi

    local IMAGE_TAG="long-running-smoke:test"
    local TEMP_REPO=""

    # Cleanup at end of function, not via EXIT trap (which fires at script scope)
    cleanup_docker() {
        log_info "Cleaning up Docker resources..."
        docker rmi "$IMAGE_TAG" 2>/dev/null || true
        if [[ -n "$TEMP_REPO" && -d "$TEMP_REPO" ]]; then
            rm -rf "$TEMP_REPO"
        fi
    }

    log_info "Building image from .devcontainer/..."
    local DOCKERFILE="$DEVCONTAINER_DIR/Dockerfile"
    if [[ -f "$DOCKERFILE" ]]; then
        docker build -t "$IMAGE_TAG" -f "$DOCKERFILE" "$DEVCONTAINER_DIR"
    else
        log_warn "No Dockerfile found in .devcontainer/, using generic image"
        docker build -t "$IMAGE_TAG" - <<'DOCKERFILE'
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
DOCKERFILE
    fi

    log_info "Initializing bare git repo in temp dir..."
    TEMP_REPO="$(mktemp -d)"
    git init --bare "$TEMP_REPO/repo.git" >/dev/null 2>&1

    log_info "Pushing project state to bare repo..."
    local TEMP_CLONE="$(mktemp -d)"
    git clone "$TEMP_REPO/repo.git" "$TEMP_CLONE/work" >/dev/null 2>&1
    cp -r "$PROJECT_ROOT"/{scripts,tests,.devcontainer} "$TEMP_CLONE/work/" 2>/dev/null || true
    (
        cd "$TEMP_CLONE/work"
        git add -A >/dev/null 2>&1
        git -c user.email="smoke@test" -c user.name="Smoke Test" commit -m "smoke test" >/dev/null 2>&1
        git push origin HEAD >/dev/null 2>&1
    )
    rm -rf "$TEMP_CLONE"

    log_info "Running container with smoke test command..."
    local OUTPUT
    OUTPUT=$(docker run --rm "$IMAGE_TAG" echo 'smoke test passed' 2>&1)

    if [[ "$OUTPUT" == *"smoke test passed"* ]]; then
        log_info "Docker smoke test PASSED"
        cleanup_docker
        return 0
    else
        log_error "Docker smoke test FAILED. Output: $OUTPUT"
        cleanup_docker
        return 1
    fi
}

# ── DevPod smoke test ─────────────────────────────────────

devpod_smoke_test() {
    log_info "=== DevPod Smoke Test ==="

    if ! command -v devpod &>/dev/null; then
        log_warn "DevPod CLI is not installed. Skipping DevPod test."
        log_warn "Install from: https://devpod.sh/docs/getting-started/install"
        return 0
    fi

    if ! command -v docker &>/dev/null || ! docker info &>/dev/null; then
        log_warn "Docker is required as local fallback provider. Skipping DevPod test."
        return 0
    fi

    local WORKSPACE_NAME="long-running-smoke-$$"

    cleanup_devpod() {
        log_info "Cleaning up DevPod workspace..."
        devpod stop "$WORKSPACE_NAME" 2>/dev/null || true
        devpod delete "$WORKSPACE_NAME" --force 2>/dev/null || true
    }

    log_info "Starting DevPod workspace with --provider docker..."
    devpod up "$PROJECT_ROOT" \
        --provider docker \
        --id "$WORKSPACE_NAME" \
        --ide none \
        2>&1 | while IFS= read -r line; do log_info "  devpod: $line"; done

    log_info "Running smoke command via SSH..."
    local OUTPUT
    OUTPUT=$(devpod ssh "$WORKSPACE_NAME" --command "echo 'devpod smoke test passed'" 2>&1)

    if [[ "$OUTPUT" == *"devpod smoke test passed"* ]]; then
        log_info "DevPod smoke test PASSED"
        cleanup_devpod
        return 0
    else
        log_error "DevPod smoke test FAILED. Output: $OUTPUT"
        cleanup_devpod
        return 1
    fi
}

# ── Main ──────────────────────────────────────────────────

EXIT_CODE=0

if [[ "$RUN_DOCKER" == true ]]; then
    if ! docker_smoke_test; then
        EXIT_CODE=1
    fi
fi

if [[ "$RUN_DEVPOD" == true ]]; then
    if ! devpod_smoke_test; then
        EXIT_CODE=1
    fi
fi

if [[ "$EXIT_CODE" -eq 0 ]]; then
    log_info "All smoke tests passed."
else
    log_error "Some smoke tests failed."
fi

exit $EXIT_CODE
