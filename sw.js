const CACHE = 'quizlet-pro-v5';
const SHELL = ['/', '/index.html', '/js/study-utils.js', '/js/database.js', '/js/navigation.js',
    '/js/session.js', '/js/cloud.js', '/js/editor.js', '/js/bookmarklet.js'];
const MANIFEST = '/data/sets.json';

async function saveResponse(cache, key, response) {
    // Storage quota, private mode or disk errors must not turn a successful fetch into an outage.
    try { await cache.put(key, response.clone()); } catch (error) { console.warn('Offline cache write:', error); }
}

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE);
        await cache.addAll(SHELL);
        // An unavailable/malformed manifest or one missing set must not block shell installation.
        try {
            const response = await fetch(MANIFEST, { cache: 'no-cache' });
            if (!response.ok) return;
            const sets = await response.clone().json();
            if (!Array.isArray(sets)) return;
            await saveResponse(cache, MANIFEST, response);
            await Promise.allSettled(sets.filter(set => set && /^[A-Za-z0-9_-]{1,120}$/.test(String(set.id)))
                .map(set => cache.add(`/data/sets/${encodeURIComponent(set.id)}.json`)));
        } catch (error) { console.warn('Offline set preload:', error); }
        // Activate new app code promptly instead of leaving open tabs on a stale worker.
        await self.skipWaiting();
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const names = await caches.keys();
        const upgrading = names.some(name => name.startsWith('quizlet-pro-') && name !== CACHE);
        for (const name of names) {
            if (name.startsWith('quizlet-pro-') && name !== CACHE) await caches.delete(name);
        }
        await self.clients.claim();
        if (upgrading) {
            const clients = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
            await Promise.allSettled(clients.map(client => client.navigate(client.url)));
        }
    })());
});

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
    const asset = SHELL.includes(url.pathname) || url.pathname === MANIFEST || /^\/data\/sets\/[A-Za-z0-9_-]+\.json$/.test(url.pathname);
    if (!asset && request.mode !== 'navigate') return;
    event.respondWith((async () => {
        let cache;
        try { cache = await caches.open(CACHE); } catch { /* Network remains usable without storage. */ }
        const saved = async () => {
            if (!cache) return null;
            try {
                return await cache.match(url.pathname) || (request.mode === 'navigate' ? await cache.match('/') : null);
            } catch { return null; }
        };
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);
            let response;
            try { response = await fetch(request, { signal: controller.signal }); }
            finally { clearTimeout(timeout); }
            if (response.ok) {
                if (cache && asset) await saveResponse(cache, url.pathname, response);
                return response;
            }
            return await saved() || response;
        } catch {
            return await saved() || new Response('Chưa lưu tài nguyên này để dùng ngoại tuyến.', { status: 503 });
        }
    })());
});
