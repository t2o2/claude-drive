FROM python:3.12-slim

# System deps matching devcontainer.json features
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Node.js LTS (for Claude CLI)
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude CLI
RUN npm install -g @anthropic-ai/claude-code

# Copy scripts to a separate location (not workspace root to allow clean git clone)
COPY scripts/ /opt/claude-drive/scripts/
COPY .claude/ /opt/claude-drive/.claude/
RUN chmod +x /opt/claude-drive/scripts/entrypoint.sh

# Create non-root user for agent operations
RUN useradd -m -s /bin/bash claude && \
    mkdir -p /workspace /home/claude/.claude && \
    chown -R claude:claude /workspace /home/claude/.claude

# Set PATH so scripts are accessible
ENV PATH="/opt/claude-drive/scripts:$PATH"

USER claude

# Git config for agent commits (must be after USER switch)
RUN git config --global user.name "Claude Agent" \
    && git config --global user.email "agent@claude-drive"

WORKDIR /workspace
