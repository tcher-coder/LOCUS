# LOCUS bridge: Python (bridge) + Node (claude CLI) + ffmpeg/yt-dlp (видео)
FROM node:22-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-venv git ffmpeg ca-certificates curl gosu \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI (его спавнит Agent SDK)
RUN npm install -g @anthropic-ai/claude-code

# Непривилегированный пользователь (Agent SDK запрещает --dangerously-skip-permissions под root)
RUN groupadd -r locus && useradd -r -g locus -m -d /home/locus -s /bin/bash locus

# Глобальный скилл /watch (bradautomates/claude-video) — ставим от locus
USER locus
ENV HOME=/home/locus
RUN npx -y skills add bradautomates/claude-video -g \
    && echo "--- installed skills ---" && ls -R /home/locus/.claude/skills 2>/dev/null || true
USER root

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
