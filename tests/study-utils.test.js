const { test } = require('node:test');
const assert = require('node:assert/strict');
const { normalizeSet, answersMatch, choiceOptions } = require('../js/study-utils.js');

test('normalization removes repeated pages, keeps distinct cards and zero IDs', () => {
    const a = { id: 0, term: 'one', definition: 'một', image: 'https://example.com/a.png' };
    const set = normalizeSet({ id: 123, cards: [a, a, { ...a, term: 'different' }] });
    assert.equal(set.id, '123');
    assert.equal(set.cards.length, 2);
    assert.equal(set.cards[0].id, 0);
    assert.notEqual(set.cards[1].id, 0);
    assert.equal(set.cards[0].image, a.image);
    assert.equal(set.numTerms, 2);
});

test('invalid imports fail instead of producing unusable cards', () => {
    assert.throws(() => normalizeSet({ cards: [null] }));
    assert.throws(() => normalizeSet({ cards: [{ term: {}, definition: 'x' }] }));
    assert.throws(() => normalizeSet({ cards: [] }));
});

test('grading accepts formatting and complete synonyms, not substrings or wrong equations', () => {
    assert.equal(answersMatch('ＨＥＬＬＯ world!', 'hello world'), true);
    assert.equal(answersMatch('xe hơi', 'ô tô; xe hơi'), true);
    assert.equal(answersMatch('not a cat', 'cat; feline'), false);
    assert.equal(answersMatch('x', 'x = y'), false);
    assert.equal(answersMatch('12', '1/2'), false);
    assert.equal(answersMatch('5', '-5'), false);
    assert.equal(answersMatch('15', '1.5'), false);
    assert.equal(answersMatch('1.5', '15'), false);
    assert.equal(answersMatch(undefined, 'undefined'), false);
    assert.equal(answersMatch('!!!', '???'), false);
});

test('text imports preserve the full right-hand side and report every invalid line', () => {
    const { parseText } = require('../js/study-utils.js');
    const parsed = parseText('Ratio\tx = 1: 2\ninvalid\nURL\thttps://example.com?a=1\nword - meaning - extra');
    assert.deepEqual(parsed.invalidLines, [2]);
    assert.equal(parsed.cards[0].definition, 'x = 1: 2');
    assert.equal(parsed.cards[1].definition, 'https://example.com?a=1');
    assert.equal(parsed.cards[2].definition, 'meaning - extra');
});

test('numeric answer choices preserve decimal distinctions', () => {
    const options = choiceOptions([{ definition: '1.5' }, { definition: '15' }], '1.5', 'definition');
    assert.equal(options.length, 2);
});

test('SRS schedules increasing intervals and returns only due complete cards', () => {
    const { gradeCard, reviewQueue } = require('../js/study-utils.js');
    const now = 1000;
    assert.equal(gradeCard({ mastery: 0 }, true, now).nextReview, now + 300000);
    assert.equal(gradeCard({ mastery: 1 }, true, now).interval, 1);
    assert.equal(gradeCard({ mastery: 2, interval: 20 }, true, now).interval, 30);
    assert.equal(gradeCard({ mastery: 2 }, false, now).nextReview, now);
    const cards = [
        { id: 1, term: 'one', definition: 'một', mastery: 0, nextReview: 0 },
        { id: 2, term: 'two', definition: 'hai', mastery: 2, nextReview: now - 1 },
        { id: 3, term: 'three', definition: 'ba', mastery: 1, nextReview: now + 1 },
        { id: 4, term: 'missing', definition: '', mastery: 0 }
    ];
    assert.deepEqual(reviewQueue(cards, now).map(c => c.id), [2, 1]);
});

test('choice answers are unique even when definitions repeat', () => {
    const cards = ['cat', 'CAT', 'dog', 'Dog', 'bird', 'fish'].map(definition => ({ definition }));
    const options = choiceOptions(cards, 'cat', 'definition');
    assert.equal(options.length, 4);
    assert.equal(new Set(options.map(s => s.toLowerCase())).size, 4);
    assert.ok(options.includes('cat'));
});

test('share links preserve Unicode content and images without owner or progress data', async () => {
    const { createShareToken, readShareToken } = require('../js/study-utils.js');
    const original = { id: 'private-source-id', title: '日本語: Giới thiệu', description: 'Dòng 1\nDòng 2',
        cloudAccount: 'private-account', localRevision: 'private-revision', ownerEmail: 'private@example.test',
        cards: [{ id: 'private-card-id', term: '自己紹介、Giới thiệu bản thân, TỰ KỶ THIỆU GIỚI',
            definition: 'じこしょうかい', image: 'https://example.org/intro.png', mastery: 2, starred: true,
            nextReview: 123456, incorrectCount: 5 }] };
    const token = await createShareToken(original);
    assert.match(token, /^1[gj]\.[A-Za-z0-9_-]+$/);
    const received = await readShareToken(token);
    assert.match(received.id, /^shared_[a-f0-9]{64}$/);
    assert.notEqual(received.id, original.id);
    assert.equal(received.title, original.title);
    assert.equal(received.description, original.description);
    assert.equal(received.cards[0].term, original.cards[0].term);
    assert.equal(received.cards[0].definition, original.cards[0].definition);
    assert.equal(received.cards[0].image, original.cards[0].image);
    const encoded = Buffer.from(token.slice(3), 'base64url');
    const payload = (token.startsWith('1g.') ? require('node:zlib').gunzipSync(encoded) : encoded).toString('utf8');
    for (const value of ['private-source-id', 'private-card-id', 'private-account', 'private-revision', 'private@example.test', 'mastery', 'starred', 'incorrectCount']) {
        assert.equal(JSON.stringify(received).includes(value), false, value);
        assert.equal(payload.includes(value), false, value);
    }
    assert.equal((await readShareToken(await createShareToken(original))).id, received.id);
});

test('share reader supports plain payloads and ignores supplied IDs and private metadata', async () => {
    const { readShareToken } = require('../js/study-utils.js');
    const token = '1j.' + Buffer.from(JSON.stringify({ id: 'existing-local-set', title: 'Bản chia sẻ',
        cloudAccount: 'someone-else', cards: [{ id: 0, term: '名前', definition: 'なまえ', mastery: 2 }] })).toString('base64url');
    const received = await readShareToken(token);
    assert.notEqual(received.id, 'existing-local-set');
    assert.equal(received.cloudAccount, undefined);
    assert.equal(received.cards[0].mastery, undefined);
});

test('share links reject malformed, incomplete and oversized payloads', async () => {
    const { createShareToken, readShareToken } = require('../js/study-utils.js');
    for (const value of ['', '2g.abc', '1g.bad!', '1g.' + 'a'.repeat(64001), '1j.bm90LWpzb24']) {
        await assert.rejects(readShareToken(value));
    }
    await assert.rejects(createShareToken({ title: 'Empty', cards: [] }));
    await assert.rejects(createShareToken({ cards: [{ term: 'missing', definition: '' }] }));
    const huge = { cards: [{ term: 'oversized', definition: 'x'.repeat(2 * 1024 * 1024) }] };
    await assert.rejects(createShareToken(huge), /2 MB/);
    const compressed = require('node:zlib').gzipSync(JSON.stringify(huge)).toString('base64url');
    await assert.rejects(readShareToken('1g.' + compressed), /2 MB/);
    const random = require('node:crypto').randomBytes(60000).toString('hex');
    await assert.rejects(createShareToken({ cards: [{ term: 'long link', definition: random }] }), /quá lớn/);
});
