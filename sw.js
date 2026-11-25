const CACHE = 'quizlet-pro-v3';
const SHELL = ['/', '/index.html', '/js/study-utils.js', '/js/database.js', '/js/navigation.js',
    '/js/session.js', '/js/cloud.js', '/js/editor.js', '/js/bookmarklet.js', '/data/sets.json'];

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE);
        await cache.addAll(SHELL);
        const response = await cache.match('/data/sets.json');
        const sets = await response.json();
        // A single unavailable set must not prevent the application shell from installing.
        await Promise.allSettled(sets.map(set => cache.add(`/data/sets/${encodeURIComponent(set.id)}.json`)));
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        for (const name of await caches.keys()) {
            if (name.startsWith('quizlet-pro-') && name !== CACHE) await caches.delete(name);
        }
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
    const asset = SHELL.includes(url.pathname) || /^\/data\/sets\/[A-Za-z0-9_-]+\.json$/.test(url.pathname);
    if (!asset && request.mode !== 'navigate') return;
    event.respondWith((async () => {
        const cache = await caches.open(CACHE);
        try {
            const response = await fetch(request, { signal: AbortSignal.timeout(5000) });
            if (response.ok) {
                await cache.put(request, response.clone());
                return response;
            }
            return await cache.match(request) || response;
        } catch {
            const saved = await cache.match(request) || (request.mode === 'navigate' ? await cache.match('/') : null);
            return saved || new Response('Chưa lưu tài nguyên này để dùng ngoại tuyến.', { status: 503 });
        }
    })());
});
