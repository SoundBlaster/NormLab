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
RUN npm run build \
    && mkdir -p /var/lib/normlab \
    && chown node:node /var/lib/normlab

USER node
EXPOSE 4317
VOLUME ["/var/lib/normlab"]
CMD ["npm", "start"]
