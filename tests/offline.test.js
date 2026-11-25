const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

function worker(overrides = {}) {
    const events = {};
    const records = new Map();
    const cache = {
        addAll: async () => {}, add: async () => {},
        match: async key => records.get(key), put: async (key, response) => records.set(key, response)
    };
    const context = {
        self: { location: { origin: 'http://localhost' }, addEventListener: (type, cb) => events[type] = cb,
            clients: { claim: async () => {} } },
        caches: { open: async () => cache, keys: async () => [], delete: async () => true },
        fetch: async () => new Response('network'), URL, Response, AbortController, setTimeout, clearTimeout,
        console: { warn: () => {} }, ...overrides
    };
    vm.runInNewContext(fs.readFileSync(require.resolve('../sw.js'), 'utf8'), context);
    return { events, cache, records, context };
}

async function fetchEvent(w, path, mode = 'cors') {
    let response;
    w.events.fetch({ request: { url: `http://localhost${path}`, method: 'GET', mode },
        respondWith: promise => response = promise });
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

test('service worker ignores query strings for saved shell and set fallback', async () => {
    const w = worker({ fetch: async () => { throw new Error('offline'); } });
    w.records.set('/js/database.js', new Response('saved module'));
    w.records.set('/', new Response('saved shell'));
    assert.equal(await (await fetchEvent(w, '/js/database.js?v=2')).text(), 'saved module');
    assert.equal(await (await fetchEvent(w, '/?offline=1', 'navigate')).text(), 'saved shell');
    assert.equal((await fetchEvent(w, '/data/sets/unseen.json')).status, 503);
});

test('service worker malformed or unavailable manifests do not fail installation', async () => {
    for (const response of [new Response('{bad'), new Response('{}'), new Response('missing', { status: 404 })]) {
        const w = worker({ fetch: async () => response });
        let installation;
        w.events.install({ waitUntil: promise => installation = promise });
        await installation;
    }
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
