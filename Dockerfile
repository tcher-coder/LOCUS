# LOCUS bridge: Python (bridge) + Node (claude CLI) + ffmpeg/yt-dlp (видео)
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/root

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git ffmpeg ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (его спавнит Agent SDK)
RUN npm install -g @anthropic-ai/claude-code

# Глобальный скилл /watch (bradautomates/claude-video)
RUN npx -y skills add bradautomates/claude-video -g \
    && echo "--- installed skills ---" && ls -R /root/.claude/skills 2>/dev/null || true

WORKDIR /app
COPY bridge/requirements.txt bridge/requirements.txt
RUN python3 -m venv /opt/venv \
    && pip install --no-cache-dir -r bridge/requirements.txt yt-dlp

COPY bridge/ bridge/
COPY prompts/ prompts/
COPY vault.template/ vault.template/
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
