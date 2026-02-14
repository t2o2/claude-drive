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

# Git config for agent commits
RUN git config --global user.name "Claude Agent" \
    && git config --global user.email "agent@claude-drive"

WORKDIR /workspace
