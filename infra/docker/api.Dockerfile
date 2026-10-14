# Veridoc AI API gateway (NestJS). The public edge.
FROM node:20-alpine AS build
WORKDIR /app

# Install workspace dependencies (whole monorepo context; .dockerignore trims it).
COPY . .
RUN npm ci
RUN npm run build:contracts && npm run build --workspace @veridoc/api

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production

# Copy the installed workspace (node_modules includes the @veridoc/contracts
# symlink to packages/contracts/dist, which we built above).
COPY --from=build /app ./

# Run as the unprivileged user that ships with the base image (never root).
USER node

EXPOSE 3000
CMD ["node", "apps/api/dist/main.js"]
