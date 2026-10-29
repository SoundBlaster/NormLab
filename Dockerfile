FROM node:22.19.0-bookworm-slim

ENV NODE_ENV=production \
    ELAN_HOME=/home/node/.elan \
    PATH=/home/node/.elan/bin:${PATH} \
    HOST=0.0.0.0 \
    PORT=4317 \
    NORMLAB_DATA_DIR=/var/lib/normlab

ARG VITE_BASE_PATH=/
ENV VITE_BASE_PATH=$VITE_BASE_PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --chown=node:node package.json package-lock.json ./
RUN npm ci --include=dev

COPY --chown=node:node lean-toolchain ./
RUN curl -fsSL https://elan.lean-lang.org/elan-init.sh \
    | su node -s /bin/sh -c 'sh -s -- -y --default-toolchain none' \
    && su node -s /bin/sh -c 'cd /app && elan toolchain install "$(cat lean-toolchain)"' \
    && su node -s /bin/sh -c 'lean --version | grep -F "version 4.30.0"'

COPY --chown=node:node . .
ARG NORMLAB_BUILD_REVISION
RUN npm run build \
    && mkdir -p /var/lib/normlab \
    && chown node:node /var/lib/normlab

# Fixed parking Lean runtime: compiled once with the verifier's flags, gated, and
# pinned by SHA-256 in manifest.json. -M only caps memory; the .olean bytes are identical.
RUN su node -s /bin/sh -c 'cd /app && NORMLAB_LEAN_MEMORY_MB=1024 npm run parking:runtime:build -- --output /tmp/normlab-lean-runtime' \
    && mv /tmp/normlab-lean-runtime /app/.lean-runtime \
    && chown -R root:root /app/.lean-runtime \
    && chmod -R a=rX /app/.lean-runtime

USER node
EXPOSE 4317
VOLUME ["/var/lib/normlab"]
CMD ["npm", "start"]
