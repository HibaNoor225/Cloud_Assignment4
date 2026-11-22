FROM node:20-alpine

ARG APP_VERSION=1.0
ENV NODE_ENV=production \
    PORT=3000 \
    APP_VERSION=${APP_VERSION}

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force

COPY --chown=node:node . .

# The official node image ships an unprivileged "node" user (uid 1000).
USER node

EXPOSE 3000
CMD ["node", "server.js"]
