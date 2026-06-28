const CACHE = 'se-v5-2'

const PRECACHE = [
    '/app.html',
    '/css/tokens.css',
    '/css/reset.css',
    '/css/layout.css',
    '/css/typography.css',
    '/css/components/buttons.css',
    '/css/components/badges.css',
    '/css/components/cards.css',
    '/css/components/tables.css',
    '/css/components/forms.css',
    '/css/components/modals.css',
    '/css/components/charts.css',
    '/css/components/feedback.css',
    '/css/components/progress.css',
    '/js/preact.min.js',
    '/js/preact-hooks.min.js',
    '/js/htm.min.js',
    '/js/chartjs.min.js',
    '/js/utils.js',
    '/js/charts.js',
    '/js/api.js',
    '/js/store.js',
    '/js/components.js',
    '/js/pages/now.js',
    '/js/pages/positions.js',
    '/js/pages/performance.js',
    '/js/pages/universe.js',
    '/js/pages/system.js',
    '/js/app.js',
    '/favicon.svg',
    '/icons/icon-192.png',
    '/icons/icon-512.png',
    '/manifest.json',
]

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE)
            .then(cache => cache.addAll(PRECACHE))
            .then(() => self.skipWaiting())
    )
})

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(
                keys.filter(k => k !== CACHE).map(k => caches.delete(k))
            )
        ).then(() => self.clients.claim())
    )
})

self.addEventListener('fetch', e => {
    const url = new URL(e.request.url)

    if (e.request.method !== 'GET') return
    if (url.pathname.startsWith('/api/'))     return
    if (url.pathname.startsWith('/ws/'))      return
    if (url.pathname.startsWith('/auth/'))    return
    if (url.pathname.startsWith('/webhook/')) return

    e.respondWith(
        caches.match(e.request).then(cached => {
            if (cached) return cached
            return fetch(e.request).then(response => {
                if (!response || response.status !== 200) return response
                const clone = response.clone()
                caches.open(CACHE).then(cache => cache.put(e.request, clone))
                return response
            })
        })
    )
})