#!/bin/sh
# Regenerate the SPA's runtime config (window.__VERIDOC_ENV__) from the container
# environment, so one built image serves any environment. The official nginx
# image runs every /docker-entrypoint.d/*.sh before starting nginx.
#
# API_BASE_URL: absolute gateway URL (e.g. https://api.example.com) OR empty for
# same-origin "/api" routing behind an ingress (the recommended default).
set -eu

api_base_url="${API_BASE_URL:-}"
cat > /usr/share/nginx/html/env.js <<EOF
window.__VERIDOC_ENV__ = { API_BASE_URL: "${api_base_url}" };
EOF
