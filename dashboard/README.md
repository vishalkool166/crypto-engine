# Signal Engine Dashboard (Cloudflare Pages)

This source was merged from the separate frontend GitHub repo into the backend monorepo under `dashboard/`. The old original colors and Outfit/Geist typography are preserved. Build assets output to **`dist/`**, never to the backend's existing `frontend/` directory.

```bash
npm ci
npm run lint
npx tsc -b
npm run build
npm run dev
```

Use Node 22. For Cloudflare Git integration select root `dashboard`, build command `npm run build`, output `dist`, and set `VITE_API_URL` / `VITE_WS_URL` to the AWS API and websocket origins. Vite dev proxies to localhost unless explicitly overridden. Never put private tokens in `VITE_*`; those values become public browser JavaScript.

The PWA caches build assets only, not authenticated trading API responses. Demonstration pages should be labeled as such. See `../docs/operations/AWS_CLOUDFLARE_ROLLOUT.md` for deployment gates and cookie/OAuth requirements.
