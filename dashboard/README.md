# Signal Engine dashboard

Editable React 18, TypeScript, and Vite application. This directory is the Cloudflare Pages project root; the production build is written to `dist/`.

Run locally with `npm ci && npm run dev`. Build with `npm ci && npm run build`. For Cloudflare Pages, set the project root to this directory, the build command to `npm ci && npm run build`, and the output directory to `dist`.

The production app sends API, authentication, and WebSocket traffic to the current origin. Forward `/api/*`, `/auth/*`, and `/ws/*` to the backend.
