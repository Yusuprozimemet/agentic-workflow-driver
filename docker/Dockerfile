# The image each step session runs in (docs/container.md). Build arguments, all required:
# CLAUDE_VERSION, the Claude Code version; GIT_NAME and GIT_EMAIL, the commit identity.
FROM node:22-trixie-slim
ARG CLAUDE_VERSION
ARG GIT_NAME
ARG GIT_EMAIL
RUN test -n "$CLAUDE_VERSION" && test -n "$GIT_NAME" && test -n "$GIT_EMAIL"
RUN apt-get update \
 && apt-get install -y --no-install-recommends git python3 python3-venv python-is-python3 ca-certificates procps gh \
 && rm -rf /var/lib/apt/lists/*
# Python in a virtual environment first on PATH, owned by node, so the session can pip install the project.
RUN python3 -m venv /opt/venv && chown -R node:node /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_VERSION}
# The checkout is a bind mount owned by root, CRLF on Windows: without these git refuses it or reads every file as changed.
RUN git config --system safe.directory /work \
 && git config --system core.autocrlf true \
 && git config --system core.filemode false \
 && git config --system user.name "$GIT_NAME" \
 && git config --system user.email "$GIT_EMAIL" \
 && git config --system credential.helper '!gh auth git-credential'
WORKDIR /work
USER node
