// Bump the shell revision and script URLs together when releasing app changes.
const CACHE = 'quizlet-pro-v6';
const DATA_CACHE = 'quizlet-pro-data-v1';
const SHELL = ['/', '/js/study-utils.js?v=6', '/js/database.js?v=6', '/js/navigation.js?v=6',
    '/js/session.js?v=6', '/js/cloud.js?v=6', '/js/editor.js?v=6', '/js/bookmarklet.js?v=6'];
const SHELL_PATHS = new Set(SHELL.map(path => new URL(path, self.location.origin).pathname));
const MANIFEST = '/data/sets.json';

async function saveResponse(cache, key, response) {
    // Storage quota, private mode or disk errors must not turn a successful fetch into an outage.
    try { await cache.put(key, response.clone()); } catch (error) { console.warn('Offline cache write:', error); }
}

self.addEventListener('install', event => {
    event.waitUntil((async () => {
        const cache = await caches.open(CACHE);
        await cache.addAll(SHELL.map(path => new Request(new URL(path, self.location.origin), { cache: 'reload' })));
        const controller = new AbortController();
        let timer;
        try {
            // Optional downloads must not keep the previous worker active indefinitely.
            await Promise.race([(async () => {
                const data = await caches.open(DATA_CACHE);
                const response = await fetch(MANIFEST, { cache: 'no-cache', signal: controller.signal });
                if (!response.ok) return;
                const sets = await response.clone().json();
                if (!Array.isArray(sets)) return;
                await saveResponse(data, MANIFEST, response);
                await Promise.allSettled(sets.filter(set => set && /^[A-Za-z0-9_-]{1,120}$/.test(String(set.id)))
                    .map(async set => {
                        const path = `/data/sets/${encodeURIComponent(set.id)}.json`;
                        const response = await fetch(path, { cache: 'no-cache', signal: controller.signal });
                        if (response.ok && Array.isArray((await response.clone().json())?.cards)) {
                            await saveResponse(data, path, response);
                        }
                    }));
            })(), new Promise(resolve => {
                timer = setTimeout(() => { controller.abort(); resolve(); }, 2500);
            })]);
        } catch (error) { console.warn('Offline set preload:', error); }
        finally {
            clearTimeout(timer);
            await self.skipWaiting();
        }
    })());
});

self.addEventListener('activate', event => {
    event.waitUntil((async () => {
        const names = await caches.keys();
        const data = await caches.open(DATA_CACHE);
        for (const name of names) {
            if (!name.startsWith('quizlet-pro-') || name === CACHE || name === DATA_CACHE) continue;
            try {
                // Preserve previously downloaded sets when upgrading the old combined cache.
                const previous = await caches.open(name);
                for (const request of await previous.keys()) {
                    const path = new URL(request.url).pathname;
                    if (path.startsWith('/data/') && !await data.match(path)) {
                        await data.put(path, await previous.match(request));
                    }
                }
                await caches.delete(name);
            } catch (error) { console.warn('Offline cache migration:', error); }
        }
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', event => {
    const request = event.request;
    const url = new URL(request.url);
    if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;
    const isData = url.pathname === MANIFEST || /^\/data\/sets\/[A-Za-z0-9_-]+\.json$/.test(url.pathname);
    const navigation = request.mode === 'navigate' || url.pathname === '/index.html' || url.pathname === '/';
    const asset = SHELL_PATHS.has(url.pathname) || navigation || isData;
    if (!asset && request.mode !== 'navigate') return;
    const key = isData ? url.pathname : navigation ? '/' : url.pathname + url.search;
    const cacheName = isData ? DATA_CACHE : CACHE;
    event.respondWith((async () => {
        const saved = async () => {
            try { return await (await caches.open(cacheName)).match(key); }
            catch { return null; }
        };
        try {
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);
            let response;
            try { response = await fetch(request, { cache: 'no-cache', signal: controller.signal }); }
            finally { clearTimeout(timeout); }
            if (response.ok) {
                const copy = response.clone();
                event.waitUntil((async () => {
                    try {
                        if (isData) {
                            const value = await copy.clone().json();
                            if (!(url.pathname === MANIFEST ? Array.isArray(value) : Array.isArray(value?.cards))) return;
                        }
                        await saveResponse(await caches.open(cacheName), key, copy);
                    } catch (error) { console.warn('Offline cache refresh:', error); }
                })());
                return response;
            }
            return response.status >= 500 ? await saved() || response : response;
        } catch {
            return await saved() || new Response('Chưa lưu tài nguyên này để dùng ngoại tuyến.', { status: 503 });
        }
    })());
});
