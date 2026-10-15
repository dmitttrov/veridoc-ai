# Veridoc AI API gateway (NestJS). The public edge.
# Base image pinned by digest for reproducible builds.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build
WORKDIR /app

# Install workspace dependencies (whole monorepo context; .dockerignore trims it).
COPY . .
RUN npm ci
RUN npm run build:contracts && npm run build --workspace @veridoc/api
# Drop dev dependencies so only production deps remain in node_modules.
RUN npm prune --omit=dev

# --- Runtime: ship ONLY production deps + built artifacts, not the whole
# monorepo or any dev toolchain (this is the public edge; keep it minimal). ---
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293
WORKDIR /app
ENV NODE_ENV=production

# Pruned production node_modules (the @veridoc/contracts workspace symlink
# points at packages/contracts, copied below so it resolves to real files).
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/packages/contracts/package.json ./packages/contracts/package.json
COPY --from=build /app/packages/contracts/dist ./packages/contracts/dist
COPY --from=build /app/apps/api/package.json ./apps/api/package.json
COPY --from=build /app/apps/api/dist ./apps/api/dist

# Run as the unprivileged user that ships with the base image (never root).
USER node

EXPOSE 3000
CMD ["node", "apps/api/dist/main.js"]
