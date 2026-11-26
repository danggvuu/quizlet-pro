const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function worker(overrides = {}) {
    const events = {};
    const stores = new Map();
    const state = { skipped: 0, claimed: 0 };
    const pending = [];
    const keyOf = key => {
        const url = new URL(typeof key === 'string' ? key : key.url, 'http://localhost');
        return url.pathname + url.search;
    };
    const open = async name => {
        if (!stores.has(name)) stores.set(name, new Map());
        const records = stores.get(name);
        return {
            addAll: async () => {},
            match: async key => records.get(keyOf(key))?.clone(),
            put: async (key, response) => records.set(keyOf(key), response.clone()),
            keys: async () => [...records.keys()].map(path => new Request(`http://localhost${path}`))
        };
    };
    const records = new Map();
    stores.set('quizlet-pro-v12', records);
    const cache = {
        addAll: async () => {},
        match: async key => records.get(keyOf(key))?.clone(),
        put: async (key, response) => records.set(keyOf(key), response.clone()),
        keys: async () => [...records.keys()].map(path => new Request(`http://localhost${path}`))
    };
    const context = {
        self: { location: { origin: 'http://localhost' }, addEventListener: (type, cb) => events[type] = cb,
            clients: { claim: async () => { state.claimed++; }, matchAll: async () => [] },
            skipWaiting: async () => { state.skipped++; } },
        caches: { open: async name => name === 'quizlet-pro-v12' ? cache : open(name),
            keys: async () => [...stores.keys()], delete: async name => stores.delete(name) },
        fetch: async () => new Response('network'), URL, Request, Response, AbortController, setTimeout, clearTimeout,
        console: { warn: () => {} }, ...overrides
    };
    vm.runInNewContext(fs.readFileSync(require.resolve('../sw.js'), 'utf8'), context);
    return { events, cache, records, context, state, stores, pending,
        flush: async () => Promise.allSettled(pending.splice(0)) };
}

async function fetchEvent(w, path, mode = 'cors') {
    let response;
    w.events.fetch({ request: { url: `http://localhost${path}`, method: 'GET', mode },
        respondWith: promise => response = promise, waitUntil: promise => w.pending.push(promise) });
    return response;
}

test('service worker successful network remains successful if cache put fails', async () => {
    const w = worker();
    w.cache.put = async () => { throw new Error('quota'); };
    const response = await fetchEvent(w, '/js/database.js');
    assert.equal(response.status, 200);
    assert.equal(await response.text(), 'network');
});

test('service worker network remains usable if cache storage cannot open', async () => {
    const w = worker({ caches: { open: async () => { throw new Error('storage blocked'); } } });
    assert.equal(await (await fetchEvent(w, '/index.html')).text(), 'network');
});

test('service worker isolates script revisions and canonicalizes HTML fallback', async () => {
    const w = worker({ fetch: async () => { throw new Error('offline'); } });
    w.records.set('/js/database.js?v=11', new Response('saved module'));
    w.records.set('/js/table-import.js?v=12', new Response('saved importer'));
    w.records.set('/', new Response('saved shell'));
    assert.equal(await (await fetchEvent(w, '/js/database.js?v=11')).text(), 'saved module');
    assert.equal(await (await fetchEvent(w, '/js/table-import.js?v=12')).text(), 'saved importer');
    assert.equal((await fetchEvent(w, '/js/database.js?v=9')).status, 503);
    assert.equal(await (await fetchEvent(w, '/?offline=1', 'navigate')).text(), 'saved shell');
    assert.equal(await (await fetchEvent(w, '/index.html')).text(), 'saved shell');
    assert.equal((await fetchEvent(w, '/data/sets/unseen.json')).status, 503);
});

test('service worker malformed or unavailable manifests do not fail installation', async () => {
    for (const response of [new Response('{bad'), new Response('{}'), new Response('null'),
        new Response('missing', { status: 404 }), new Response('error', { status: 500 })]) {
        const w = worker({ fetch: async () => response });
        let installation;
        w.events.install({ waitUntil: promise => installation = promise });
        await installation;
        assert.equal(w.state.skipped, 1);
    }
});

test('optional downloads cannot indefinitely block activation', async () => {
    const w = worker({ fetch: () => new Promise(() => {}),
        setTimeout: callback => { queueMicrotask(callback); return 1; }, clearTimeout: () => {} });
    let installation;
    w.events.install({ waitUntil: promise => installation = promise });
    await installation;
    assert.equal(w.state.skipped, 1);
});

test('failed essential shell installation does not replace the active worker', async () => {
    const w = worker();
    w.cache.addAll = async () => { throw new Error('missing shell'); };
    let installation;
    w.events.install({ waitUntil: promise => installation = promise });
    await assert.rejects(installation, /missing shell/);
    assert.equal(w.state.skipped, 0);
});

test('successful network responses do not wait for cache writes', async () => {
    const w = worker();
    let release;
    w.cache.put = () => new Promise(resolve => { release = resolve; });
    const response = await fetchEvent(w, '/js/database.js?v=9');
    assert.equal(await response.text(), 'network');
    assert.equal(typeof release, 'function');
    release();
    await w.flush();
});

test('activation preserves old downloaded sets and claims tabs without navigating them', async () => {
    const w = worker();
    const previous = await w.context.caches.open('quizlet-pro-v5');
    await previous.put('/data/sets/saved.json', new Response('{"cards":[]}'));
    let activation;
    w.events.activate({ waitUntil: promise => activation = promise });
    await activation;
    assert.equal(w.state.claimed, 1);
    assert.equal(w.stores.has('quizlet-pro-v5'), false);
    const data = await w.context.caches.open('quizlet-pro-data-v1');
    assert.equal(await (await data.match('/data/sets/saved.json')).text(), '{"cards":[]}');
});

test('malformed online data does not replace the last valid offline copy', async () => {
    const w = worker({ fetch: async () => new Response('{bad') });
    const data = await w.context.caches.open('quizlet-pro-data-v1');
    await data.put('/data/sets.json', new Response('[]'));
    await fetchEvent(w, '/data/sets.json');
    await w.flush();
    assert.equal(await (await data.match('/data/sets.json')).text(), '[]');
});

test('a removed resource returns its 404 instead of stale content', async () => {
    const w = worker({ fetch: async () => new Response('removed', { status: 404 }) });
    w.records.set('/js/database.js?v=9', new Response('old module'));
    assert.equal((await fetchEvent(w, '/js/database.js?v=9')).status, 404);
});

test('service worker never intercepts APIs cross-origin resources or writes', () => {
    const w = worker();
    for (const request of [
        { method: 'GET', url: 'http://localhost/api/sets', mode: 'cors' },
        { method: 'GET', url: 'https://example.com/index.html', mode: 'navigate' },
        { method: 'POST', url: 'http://localhost/index.html', mode: 'cors' }
    ]) {
        w.events.fetch({ request, respondWith: () => assert.fail('must not intercept') });
    }
});
