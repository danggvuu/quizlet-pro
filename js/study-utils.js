/* Shared data and grading helpers; usable in browsers and Node tests. */
(function (root) {
    function shuffle(items) {
        const result = [...items];
        for (let i = result.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [result[i], result[j]] = [result[j], result[i]];
        }
        return result;
    }

    function normalizeSet(input) {
        if (!input || typeof input !== 'object' || !Array.isArray(input.cards) || !input.cards.length) {
            throw new Error('Bộ thẻ phải có danh sách cards không rỗng.');
        }
        const seen = new Map();
        const cards = [];
        input.cards.forEach((card, index) => {
            if (!card || typeof card.term !== 'string' || typeof card.definition !== 'string') {
                throw new Error(`Thẻ ${index + 1}: thuật ngữ và định nghĩa phải là văn bản.`);
            }
            if (!card.term.trim() && !card.definition.trim()) {
                throw new Error(`Thẻ ${index + 1} đang trống.`);
            }
            let id = card.id;
            if (!(typeof id === 'string' && id) && !(typeof id === 'number' && Number.isFinite(id))) {
                id = `card_${index}`;
            }
            const image = typeof card.image === 'string' && /^https?:\/\//i.test(card.image) ? card.image : '';
            const clean = { id, term: card.term, definition: card.definition, image };
            const previous = seen.get(String(id));
            if (previous) {
                if (previous.term === clean.term && previous.definition === clean.definition && previous.image === clean.image) return;
                // Keep distinct content even when a source reused its ID.
                let suffix = 1;
                while (seen.has(`${id}_${suffix}`)) suffix++;
                clean.id = `${id}_${suffix}`;
            }
            seen.set(String(clean.id), clean);
            cards.push(clean);
        });
        return {
            ...input,
            id: String(input.id ?? `set_${crypto.randomUUID()}`),
            title: typeof input.title === 'string' && input.title.trim() ? input.title.trim() : 'Học phần không tên',
            description: typeof input.description === 'string' ? input.description : '',
            numTerms: cards.length,
            cards
        };
    }

    function normalizeAnswer(value) {
        if (/[=+<>`{}\\]|\d[.,]\d|\d\s*\/\s*\d/.test(String(value))) {
            return String(value).normalize('NFKC').trim().replace(/\s+/g, ' ');
        }
        return String(value).normalize('NFKC').toLowerCase()
            .replace(/[.,!?;:"'“”‘’]/g, '').replace(/\s+/g, ' ').trim();
    }

    function answersMatch(input, target) {
        if (input == null || target == null) return false;
        if (!String(input).trim() || !String(target).trim()) return false;
        if (/[=+<>`{}\\]|\d[.,]\d|\d\s*\/\s*\d/.test(target) ||
            /[=+<>`{}\\]|\d[.,]\d|\d\s*\/\s*\d/.test(input)) {
            return String(input).normalize('NFKC').trim().replace(/\s+/g, ' ') ===
                String(target).normalize('NFKC').trim().replace(/\s+/g, ' ');
        }
        const answer = normalizeAnswer(input);
        if (!answer) return false;
        if (answer === normalizeAnswer(target)) return true;
        return String(target).split(/[,;]|\s+\/\s+/)
            .some(part => normalizeAnswer(part) === answer);
    }

    function choiceOptions(cards, correct, field) {
        const alternatives = [...new Set(cards.map(c => c[field]))]
            .filter(value => value && normalizeAnswer(value) !== normalizeAnswer(correct));
        const unique = new Map(alternatives.map(value => [normalizeAnswer(value), value]));
        return shuffle([correct, ...shuffle([...unique.values()]).slice(0, 3)]);
    }

    function parseText(text) {
        const cards = [], invalidLines = [];
        String(text).split(/\r?\n/).forEach((line, index) => {
            if (!line.trim()) return;
            // A tab is an explicit boundary. Never split the definition again.
            const separator = line.includes('\t') ? /\t/ : / {2,}| - | – | = |:\s+|,/;
            const match = separator.exec(line);
            const term = match ? line.slice(0, match.index).trim() : '';
            const definition = match ? line.slice(match.index + match[0].length).trim() : '';
            if (!term || !definition) invalidLines.push(index + 1);
            else cards.push({ id: crypto.randomUUID(), term, definition, image: '' });
        });
        return { cards, invalidLines };
    }

    function requireCompleteCards(set) {
        const index = set.cards.findIndex(c => !c.term.trim() || !c.definition.trim());
        if (index >= 0) throw new Error(`Thẻ ${index + 1} cần có cả thuật ngữ và định nghĩa.`);
        return set;
    }

    function contentKey(set) {
        return JSON.stringify([set.title, set.description || '', set.cards.map(c =>
            [String(c.id), c.term, c.definition, c.image || ''])]);
    }

    function gradeCard(card, correct, now = Date.now()) {
        const day = 24 * 60 * 60 * 1000;
        if (!correct) return { mastery: 1, nextReview: now, interval: 0 };
        if (!card.mastery) return { mastery: 1, nextReview: now + 5 * 60 * 1000, interval: 0 };
        const interval = card.mastery === 2 ? Math.min(30, Math.max(1, card.interval || 1) * 2) : 1;
        return { mastery: 2, nextReview: now + interval * day, interval };
    }

    function reviewQueue(cards, now = Date.now()) {
        const complete = cards.filter(c => c.term.trim() && c.definition.trim());
        return complete.filter(c => !c.mastery || !c.nextReview || c.nextReview <= now)
            .sort((a, b) => (a.mastery ? 0 : 1) - (b.mastery ? 0 : 1) ||
                (a.nextReview || 0) - (b.nextReview || 0));
    }

    const api = { shuffle, normalizeSet, normalizeAnswer, answersMatch, choiceOptions,
        parseText, requireCompleteCards, contentKey, gradeCard, reviewQueue };
    root.StudyUtils = api;
    if (typeof module !== 'undefined') module.exports = api;
})(globalThis);
