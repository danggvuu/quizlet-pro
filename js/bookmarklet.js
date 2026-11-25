/* Both guide buttons use this one implementation and the current app origin. */
function exportQuizletPage(destination) {
    try {
        if (!/(^|\.)quizlet\.com$/.test(location.hostname)) {
            alert('Kéo nút này lên thanh dấu trang, rồi bấm khi đang mở bộ thẻ trên Quizlet.');
            return;
        }
        let title = document.querySelector('h1')?.textContent.trim() || document.title;
        const cards = [];
        const nextData = document.getElementById('__NEXT_DATA__');
        if (nextData) {
            try {
                const data = JSON.parse(nextData.textContent);
                const state = JSON.parse(data.props.pageProps.dehydratedReduxStateKey || '{}');
                title = state.setPage?.set?.title || title;
                const items = state.studyModesCommon?.studiableData?.studiableItems || [];
                items.forEach((item, index) => {
                    const card = { id: item.id ?? index, term: '', definition: '', image: '' };
                    (item.cardSides || []).forEach(side => (side.media || []).forEach(media => {
                        if (media.type === 1 && side.label === 'word') card.term = media.plainText || '';
                        if (media.type === 1 && side.label === 'definition') card.definition = media.plainText || '';
                        if (media.type === 2) card.image = media.url || '';
                    }));
                    if (card.term && card.definition) cards.push(card);
                });
            } catch { /* Fall back to visible terms. */ }
        }
        if (!cards.length) {
            document.querySelectorAll('.SetPageTerms-term,.SetPageTerm-content,.SetPageTermsList-term').forEach((row, index) => {
                const term = row.querySelector('.SetPageTerm-wordText,[data-testid="term-word"],.SetPageTerm-smallSide')?.textContent.trim();
                const definition = row.querySelector('.SetPageTerm-definitionText,[data-testid="term-definition"],.SetPageTerm-largeSide')?.textContent.trim();
                if (term && definition) cards.push({ id: index, term, definition, image: row.querySelector('img')?.src || '' });
            });
        }
        if (!cards.length) return alert('Không tìm thấy thẻ. Hãy dùng chức năng Xuất của Quizlet và nhập văn bản hoặc JSON.');
        const payload = { id: `quizlet_${Date.now()}`, title, cards,
            description: 'Nhập các thẻ tìm thấy trên trang Quizlet. Kiểm tra số lượng với bộ gốc.' };
        const json = JSON.stringify(payload);
        if (json.length > 50000) {
            const url = URL.createObjectURL(new Blob([json], { type: 'application/json' }));
            const a = document.createElement('a');
            a.href = url; a.download = 'quizlet-export.json'; a.click();
            setTimeout(() => URL.revokeObjectURL(url), 1000);
            alert('Đã xuất JSON. Mở Quizlet Pro → Nhập thẻ → Dán nhanh → Chọn file JSON.');
        } else window.open(destination + '#data=' + encodeURIComponent(json), '_blank', 'noopener');
    } catch (error) { alert('Không xuất được thẻ: ' + error.message); }
}

const bookmarklet = `javascript:(${exportQuizletPage.toString()})(${JSON.stringify(location.origin + location.pathname)});`;
document.querySelectorAll('a[data-quizlet-export]').forEach(link => {
    link.href = bookmarklet;
    link.title = 'Kéo lên thanh dấu trang; xuất các thẻ tìm thấy trên trang Quizlet';
});
