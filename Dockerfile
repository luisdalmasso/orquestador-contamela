FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS base

# Dependencias del sistema (incluyendo gnupg para NodeSource)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl ca-certificates gnupg git bubblewrap openssh-client tmux tmuxinator wget \
      build-essential docker.io libmagic1 poppler-utils tesseract-ocr libgl1 libglib2.0-0 unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Node.js 22
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && apt-get install -y --no-install-recommends nodejs && \
    rm -rf /var/lib/apt/lists/*

# SpineDigest global
RUN npm install -g spinedigest --build-from-source

# Python deps (cacheable)
COPY requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Poppler-utils provee pdftoppm/pdftocairo para pdf2image (runtime)
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils && rm -rf /var/lib/apt/lists/*

# Rust + Bun
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    curl -fsSL https://bun.sh/install | bash
ENV PATH="/root/.cargo/bin:/root/.bun/bin:${PATH}"

# --- Submodules ---
COPY vendor/OpenHands ./vendor/OpenHands
RUN uv pip install --system --no-cache -e ./vendor/OpenHands

# oh-my-pi: instala omp-rpc (cliente Python para el RPC del agente) y compila
# los binarios nativos con bun. robomp y omp-rpc viven bajo vendor/oh-my-pi/python/.
COPY vendor/oh-my-pi ./vendor/oh-my-pi
RUN uv pip install --system --no-cache -e ./vendor/oh-my-pi/python/omp-rpc && \
    uv pip install --system --no-cache -e ./vendor/oh-my-pi/python/robomp && \
    cd vendor/oh-my-pi && bun setup

# Ponytail: las reglas viven en AGENTS.md. El "wrapper" lo implementamos en
# Python dentro del service.py (no requiere instalar paquete externo).
COPY vendor/ponytail ./vendor/ponytail

# Hermes-Agent build stage
FROM base AS hermes-build
RUN git clone --depth=1 https://github.com/NousResearch/hermes-agent.git /tmp/hermes-agent && \
    cd /tmp/hermes-agent/web && npm install && npm run build

# Final stage
FROM base

WORKDIR /app

# Copiar código con permisos correctos
COPY --chown=1000:1000 app/ app/
COPY --chown=1000:1000 config/ config/
COPY --chown=1000:1000 docs/ docs/
COPY --chown=1000:1000 README.md .
COPY --chown=1000:1000 app/hermes_profiles/ app/hermes_profiles/

# Copiar Hermes-Agent ya compilado
COPY --from=hermes-build /tmp/hermes-agent /tmp/hermes-agent
RUN uv pip install --system --no-cache /tmp/hermes-agent

# WhatsApp bridge
RUN SP="$(python3 -c "import sysconfig; print(sysconfig.get_paths()['purelib'])")" && \
    mkdir -p "$SP/scripts" && cp -r /tmp/hermes-agent/scripts/whatsapp-bridge "$SP/scripts/whatsapp-bridge" && \
    cd "$SP/scripts/whatsapp-bridge" && npm install --omit=dev --no-audit --no-fund && \
    chown -R 1000:1000 "$SP/scripts/whatsapp-bridge"

# OpenHands Agent Canvas (GUI web oficial).
# Paquete npm `@openhands/agent-canvas` (no confundir con `openhands web`
# que es una TUI textual del CLI). Este es el frontend Next.js completo
# que se ve en github.com/OpenHands/OpenHands. Conecta a nuestro
# agent-server local en :3000 vía `AGENT_SERVER_URL`.
RUN npm install -g @openhands/agent-canvas

# Entry point: copiarlo como root (puede escribir en /usr/local/bin)
# y aplicar sed/chmod antes del cambio a USER nanobot para evitar el
# "Permission denied" al crear el archivo temporal de sed -i.
COPY entrypoint_hermes.sh /usr/local/bin/entrypoint_hermes.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint_hermes.sh && \
    chmod +x /usr/local/bin/entrypoint_hermes.sh && \
    chown 1000:1000 /usr/local/bin/entrypoint_hermes.sh

# Usuario no root.
RUN useradd -m -u 1000 -s /bin/bash nanobot && \
    mkdir -p /home/nanobot/.clawteam && \
    chown -R 1000:1000 /home/nanobot /app /home/nanobot/.clawteam

USER nanobot
ENV HOME=/home/nanobot
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"
ENV CLAWTEAM_DATA_DIR=/nanobot/.clawteam
ENV CLAWTEAM_WORKSPACE=auto
ENV CLAWTEAM_SKIP_PERMISSIONS=true

# Puertos expuestos
# Hermes UI -> 3001
# OpenHands UI -> 3002
EXPOSE 3001 3002 8642 8766 8767 8768 8769 8770 9001 9119 18791

ENTRYPOINT ["entrypoint_hermes.sh"]
