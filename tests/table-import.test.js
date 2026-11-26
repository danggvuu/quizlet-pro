const { test } = require('node:test');
const assert = require('node:assert/strict');
const TableImport = require('../js/table-import.js');

test('parses quoted CSV cells, escaped quotes and line breaks', () => {
    const parsed = TableImport.parseDelimited('Term,Definition,Example\r\n"hello, world","line 1\nline 2","A ""quote"""');
    assert.equal(parsed.delimiter, ',');
    assert.deepEqual(parsed.rows, [
        ['Term', 'Definition', 'Example'],
        ['hello, world', 'line 1\nline 2', 'A "quote"']
    ]);
});

test('detects semicolon-delimited CSV and maps extra columns into the definition', () => {
    const rows = TableImport.parseDelimited('Từ;Nghĩa;Ví dụ\nnhà;house;my house').rows;
    assert.equal(TableImport.guessHasHeader(rows), true);
    const roles = TableImport.guessRoles(rows[0]);
    roles[2] = 'definition-extra';
    const mapped = TableImport.mapRows(rows, true, roles);
    assert.deepEqual(mapped.invalidRows, []);
    assert.deepEqual(mapped.cards, [{ term: 'nhà', definition: 'house\nVí dụ: my house' }]);
});

test('reports source row numbers and missing mapped values', () => {
    const rows = [['Term', 'Meaning'], ['cat', 'mèo'], ['dog', ''], ['', 'bird']];
    const mapped = TableImport.mapRows(rows, true, ['term', 'definition']);
    assert.deepEqual(mapped.cards, [{ term: 'cat', definition: 'mèo' }]);
    assert.deepEqual(mapped.invalidRows, [
        { row: 3, missing: ['định nghĩa'] },
        { row: 4, missing: ['thuật ngữ'] }
    ]);
});

test('allows a title row before the selected header row', () => {
    const rows = [['Unit 1'], ['Term', 'Definition'], ['alpha', 'first']];
    assert.equal(TableImport.guessHeaderRow(rows), 1);
    const mapped = TableImport.mapRows(rows, 1, ['term', 'definition']);
    assert.deepEqual(mapped.cards, [{ term: 'alpha', definition: 'first' }]);
    assert.deepEqual(mapped.invalidRows, []);
});

test('rejects unclosed quoted CSV cells', () => {
    assert.throws(() => TableImport.parseDelimited('term,definition\n"open,cell'), /chưa đóng/);
});

test('explicit colon separates mixed Japanese and Vietnamese text without splitting its commas', () => {
    const parsed = TableImport.parseDelimited(
        '自己紹介、Giới thiệu bản thân, TỰ KỶ THIỆU GIỚI: じこしょうかい\r\n名前、Tên, DANH TIỀN: なまえ', ':');
    const mapped = TableImport.mapRows(parsed.rows, false, ['term', 'definition']);
    assert.deepEqual(mapped.cards, [
        { term: '自己紹介、Giới thiệu bản thân, TỰ KỶ THIỆU GIỚI', definition: 'じこしょうかい' },
        { term: '名前、Tên, DANH TIỀN', definition: 'なまえ' }
    ]);
    assert.deepEqual(mapped.invalidRows, []);
});

test('detects colon, full-width colon and Japanese comma separated text', () => {
    for (const delimiter of [':', '：', '、']) {
        const parsed = TableImport.parseDelimited(`名前${delimiter}なまえ\n意味${delimiter}いみ`);
        assert.equal(parsed.delimiter, delimiter);
        assert.deepEqual(parsed.rows, [['名前', 'なまえ'], ['意味', 'いみ']]);
    }
});

test('custom separators are literal and support multiple characters and quoted cells', () => {
    for (const delimiter of ['=>', '.*', '[x]', '||']) {
        const parsed = TableImport.parseDelimited(`"a${delimiter}b"${delimiter}c\nd${delimiter}e`, delimiter);
        assert.deepEqual(parsed.rows, [[`a${delimiter}b`, 'c'], ['d', 'e']]);
    }
    for (const delimiter of ['', '\n', '\r', '"']) {
        assert.throws(() => TableImport.parseDelimited('a:b', delimiter), /phân cách cột/);
    }
});
