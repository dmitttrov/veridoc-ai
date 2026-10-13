# Veridoc AI web client (React/Vite). Built to static assets, served by nginx.
FROM node:20-alpine AS build
WORKDIR /app

# The gateway base URL is baked in at build time (it is called from the browser,
# so it must be the host-reachable gateway URL, not an internal service name).
ARG VITE_API_BASE_URL=http://localhost:3000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

COPY . .
RUN npm ci
RUN npm run build:contracts && npm run build --workspace @veridoc/web

FROM nginx:1.27-alpine
COPY infra/docker/web-nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/apps/web/dist /usr/share/nginx/html
EXPOSE 80
