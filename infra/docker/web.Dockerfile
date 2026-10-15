# Veridoc AI web client (React/Vite). Built to static assets, served by nginx.
# Base images pinned by digest for reproducible builds.
FROM node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293 AS build
WORKDIR /app

# The gateway base URL is baked in at build time (it is called from the browser,
# so it must be the host-reachable gateway URL, not an internal service name).
ARG VITE_API_BASE_URL=http://localhost:3000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm ci
RUN npm run build:contracts && npm run build --workspace @veridoc/web

FROM nginx:1.27-alpine@sha256:65645c7bb6a0661892a8b03b89d0743208a18dd2f3f17a54ef4b76fb8e2f2a10
# Patch base-image OS packages (e.g. c-ares CVE-2026-33630).
RUN apk upgrade --no-cache
COPY infra/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
