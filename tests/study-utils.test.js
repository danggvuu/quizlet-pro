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
