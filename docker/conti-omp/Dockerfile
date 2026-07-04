# syntax=docker/dockerfile:1.7-labs
# Dockerfile — thin layer agregado sobre conti-omp-base (oficial).
# Único propósito: instalar socat + netcat (necesita root) + copiar entrypoint.
# El grueso del build (Rust natives + Bun deps + omp source) viene del
# Dockerfile oficial de vendor/oh-my-pi/Dockerfile.

ARG OMP_BASE_TAG=v16.2.9
FROM conti-omp-base:${OMP_BASE_TAG} AS base

# socat + netcat-openbsd. Necesita root en build-time (no en runtime).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        socat \
        netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Confirmar installs (logs visibles en build output).
RUN socat -V 2>&1 | head -1 && nc -h 2>&1 | head -1

# Wrapper script que arranca socat con el comando omp correcto,
# leyendo env vars dinámicamente. Sin defaults hardcoded — Luis
# configura via docker-compose.conti.yml.
COPY --chown=1000:1000 entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# CRÍTICO: omp necesita HOME seteado o intenta escribir en /.omp (que
# requiere root y falla con EACCES). Crear /home/conti como ROOT antes
# de cambiar a user 1000, y chown al user no-root.
RUN mkdir -p /home/conti && chown -R 1000:1000 /home/conti
ENV HOME=/home/conti

# Volver a usuario non-root (UID 1000 = mismo que conti-backend) para
# coherencia con bind-mounts RW sobre /desarrollo, /compose, etc).
RUN mkdir -p /home/conti && chown -R 1000:1000 /home/conti
ENV HOME=/home/conti

# IMPORTANTE: el image base (conti-omp-base) tiene WORKDIR /pi (donde vive
# el código fuente de oh-my-pi). Si omp subprocess arranca con cwd=/pi, las
# tools built-in que ejecutan comandos locales (bash, git status, etc.) van
# a operar sobre /pi, no sobre el repo real de Conti. Esto rompe el flujo de
# tool bridging: omp decide no ejecutar run_salvar porque "no hay Git repo
# en /pi". WORKDIR /desarrollo hace que omp por defecto corra sobre el bind-mount
# del repo (que es /desarrollo dentro del container conti-omp).
#
# Limitación: esto fija el cwd del omp subprocess al circuit "desarrollo". Para
# los circuits produccion/backend, hace falta un omp subprocess separado por
# circuit (con --cwd=/compose o --cwd=/contenedores/conti-backend). Sprint 5+.
WORKDIR /desarrollo

# Healthcheck: socat acepta TCP en :7891.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=5 \
    CMD nc -z 127.0.0.1 7891 || exit 1

# Exponer TCP :7891 (NDJSON sobre el wire; mismo formato que `omp --mode rpc`).
EXPOSE 7891

# omp_bridge.py — wrapper Python que reemplaza socat con cwd dinámico.
# Lee OMP_CIRCUIT_CWD del env, hace chdir, y spawn omp --mode=rpc.
COPY --chown=1000:1000 omp_bridge.py /usr/local/bin/omp_bridge.py
RUN chmod +x /usr/local/bin/omp_bridge.py

# Entry: tini (señal forwarding) + nuestro wrapper script.
# El entrypoint oficial era tini + omp; acá lo reemplazamos por tini + entrypoint.sh
# que termina en omp_bridge + omp subprocess.
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]