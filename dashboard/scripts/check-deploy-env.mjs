// Independent of npm dependencies: checks build-time public API settings.
// Cloudflare Pages sets CF_PAGES=1. Local offline preview remains allowed.
const isPages = process.env.CF_PAGES === '1'
if (isPages) {
  const api = process.env.VITE_API_URL || ''
  const ws = process.env.VITE_WS_URL || ''
  const valid = (value, scheme) => {
    try {
      const u = new URL(value)
      return u.protocol === scheme && u.hostname && !u.username && !u.password &&
        u.pathname === '/' && !u.search && !u.hash
    } catch { return false }
  }
  if (!valid(api, 'https:') || !valid(ws, 'wss:')) {
    console.error('Cloudflare build requires VITE_API_URL=https://<AWS-host> and VITE_WS_URL=wss://<AWS-host>; no secrets.')
    process.exit(1)
  }
  if (new URL(api).host !== new URL(ws).host) {
    console.error('API and WebSocket must point at the same AWS host unless explicitly reviewed.')
    process.exit(1)
  }
}
console.log(isPages ? 'Cloudflare public origins validated.' : 'Local build mode; Cloudflare origin validation deferred.')
