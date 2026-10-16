# Veridoc AI web client (React/Vite). Built to static assets, served by nginx.
# Base images pinned by digest for reproducible builds.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build
WORKDIR /app

# Fallback gateway URL baked into the bundle. At RUNTIME the container overwrites
# this via window.__VERIDOC_ENV__ (see web-env.sh), so a single image serves any
# environment; this ARG only matters when runtime config is absent (e.g. the Vite
# dev server). Leave a sensible local default.
ARG VITE_API_BASE_URL=http://localhost:3000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm ci
RUN npm run build:contracts && npm run build --workspace @veridoc/web

# --- Runtime: UNPRIVILEGED nginx (non-root, listens on :8080). The gateway URL
# is injected at startup into /env.js by a /docker-entrypoint.d hook, so the same
# image is reconfigurable per environment without a rebuild. ---
FROM nginxinc/nginx-unprivileged:1.27-alpine@sha256:65e3e85dbaed8ba248841d9d58a899b6197106c23cb0ff1a132b7bfe0547e4c0
USER root
# Patch base-image OS packages (e.g. c-ares CVE-2026-33630).
RUN apk upgrade --no-cache
COPY infra/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
COPY infra/docker/web-env.sh /docker-entrypoint.d/40-veridoc-env.sh
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
# The entrypoint hook runs as uid 101 and rewrites env.js in the web root, so the
# root must be writable by that user (and by an arbitrary uid in group 0, for
# OpenShift). Make the hook executable.
RUN chmod +x /docker-entrypoint.d/40-veridoc-env.sh \
 && chown -R 101:0 /usr/share/nginx/html \
 && chmod -R g=u /usr/share/nginx/html
USER 101
EXPOSE 8080
