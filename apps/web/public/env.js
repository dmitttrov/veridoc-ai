/* global window */
// Runtime configuration placeholder for local development (Vite dev server).
// In the container image this file is regenerated at startup from environment
// variables (see infra/docker/web-env.sh). Leaving API_BASE_URL unset here makes
// the app fall back to the build-time VITE_API_BASE_URL during local dev.
window.__VERIDOC_ENV__ = window.__VERIDOC_ENV__ || {};
