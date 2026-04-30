FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# Install Node.js 20 for the WhatsApp bridge
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg git bubblewrap openssh-client tmux tmuxinator wget build-essential docker.io && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" > /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get purge -y gnupg && \
    apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Verificar instalaciones
RUN tmux -V && node --version && npm --version

# Install Python dependencies first (cached layer)
COPY requirements.txt ./
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the full source and install nanobot upstream
COPY nanobot/ nanobot/
RUN uv pip install --system --no-cache ./nanobot

# Copy conti backend sources
COPY app/ app/
COPY config/ config/
COPY docs/ docs/
COPY README.md ./README.md

# Build the WhatsApp bridge
WORKDIR /app/nanobot/bridge
RUN git config --global --add url."https://github.com/".insteadOf ssh://git@github.com/ && \
    git config --global --add url."https://github.com/".insteadOf git@github.com: && \
    npm install && npm run build
WORKDIR /app

# Instalar ClawTeam desde GitHub
RUN git clone https://github.com/HKUDS/ClawTeam.git /tmp/clawteam \
    && cd /tmp/clawteam \
    && pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -e ".[p2p]" \
    && rm -rf /tmp/clawteam

# Create non-root user and config directory
RUN useradd -m -u 1000 -s /bin/bash nanobot 

#&& \
#    mkdir -p /home/nanobot/.nanobot && \
#    chown -R nanobot:nanobot /home/nanobot /app

RUN mkdir -p /home/nanobot/.clawteam

RUN chown -R 1000:1000 /app
RUN chown -R 1000:1000 /home/nanobot
RUN chown -R 1000:1000 /home/nanobot/.clawteam


# Configurar PATH para que ambos comandos estén disponibles
ENV PATH="/usr/local/bin:${PATH}"
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Configurar variables de entorno para ClawTeam
ENV CLAWTEAM_DATA_DIR=/nanobot/.clawteam
ENV CLAWTEAM_WORKSPACE=auto
ENV CLAWTEAM_SKIP_PERMISSIONS=true

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

USER nanobot
ENV HOME=/home/nanobot

# Gateway default port
EXPOSE 18790
EXPOSE 8080
EXPOSE 8765
EXPOSE 9001

#RUN chmod +x /usr/local/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]
#CMD ["status"]
