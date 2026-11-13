import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render, showItem} from '../../ahflip/web/static/js/pages/market.js';
import {fakeApi, flush, pageShell, toastText} from './helpers.js';

const TS = 1_700_000_000;
const row = (item, name, now, extra = {}) => ({item, name, now, usual: 1000, listed: 4, sell: 50, pct: -40,
  lo: 900, hi: 1200, trend: [1000, 950, now], deal: null, ...extra});
const MARKET = {
  ts: TS, src: 'addon', counts: {below: 3, vendor: 1}, watch: [1], cut: 0.05, more: 0,
  cats: [['Recipe', ''], ['Trade Goods', 'Cloth'], ['Trade Goods', 'Leather']],
  rows: [
    row(1, 'Linen Cloth', 500, {deal: {kind: 'flip', units: null, profit: 400}}),
    row(2, null, 800, {pct: -25, sell: null, trend: [800]}),
    row(3, 'Wool Cloth', 1300, {pct: 30, trend: [5, 5], deal: {kind: 'vendor', units: 3, total: 150}}),
    row(4, 'Silk', 1000, {pct: 5, usual: null, lo: null, hi: null}),
    row(5, 'Mageweave', 1000, {pct: null}),
  ],
};
const HISTORY = {item: 1, name: 'Linen Cloth', sell: 50, min: 500, qty: 4, median: 1000, past: 6,
  points: [[TS - 3600, 1000, 3, 'api'], [TS, 500, 4, 'addon'], [TS + 60, 600, 2, 'odd']], watched: true, held: 2,
  trades: [{id: 1, ts: TS, kind: 'buy', item: 1, qty: 2, price: 500}, {id: 2, ts: TS, kind: 'sell', item: 1, qty: 1, price: 900}]};

const params = s => new URLSearchParams(s);
const tabs = main => [...main.querySelectorAll('.tab')];
const rowsOf = main => [...main.querySelectorAll('tbody tr')].map(tr => tr.dataset.item);

describe('market page', () => {
  let main, fetch;
  beforeEach(() => {
    main = pageShell();
    history.replaceState(null, '', '/market');
    fetch = fakeApi({'/api/market': MARKET, '/api/history': HISTORY, '/api/watch': (_, b) => b});
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('shows the below view by default with counts, pills and sparklines', async () => {
    await render(main, params('view=nope'));
    expect(fetch.mock.calls[0][0]).toBe('/api/market?view=below&q=&cat=');
    expect(main.querySelector('.sub').textContent).toContain('AHFlip scan');
    expect(tabs(main).map(t => t.textContent)).toEqual(['Below usual price · 3', 'Below vendor · 1', 'Rising · 0', 'All items']);
    expect(tabs(main)[0].className).toBe('tab on');
    expect(rowsOf(main)).toEqual(['5', '1', '2', '4', '3']); // by pct, lowest first (missing pct sorts lowest)
    const pills = [...main.querySelectorAll('.pill')].map(p => p.className + ' ' + p.textContent);
    expect(pills).toEqual(['pill g -40%', 'pill g2 -25%', 'pill +5%', 'pill r +30%']);
    expect(main.querySelectorAll('tbody svg')).toHaveLength(4); // row 2 has one trend value: dash
    expect(main.querySelectorAll('.star.on')).toHaveLength(1);
    expect(main.textContent).not.toContain('more not shown');
  });

  it('shows the vendor view columns and the "more" note, with an unknown source name', async () => {
    fakeApi({'/api/market': {...MARKET, src: 'other', more: 7, hidden: 4}});
    await render(main, params('view=vendor&q=cloth'));
    expect(main.querySelector('input').value).toBe('cloth');
    expect(main.querySelector('.sub').textContent).toContain('Prices from other');
    expect([...main.querySelectorAll('th')].map(t => t.textContent)).toContain('Profit / unit');
    expect(rowsOf(main)[0]).toBe('3'); // biggest total first
    expect(main.textContent).toContain('7 more not shown');
    expect(main.textContent).toContain('4 rarely listed or erratic items hidden');
  });

  it('says when there are no prices or no rows', async () => {
    fakeApi({'/api/market': {ts: null, src: null, counts: {}, rows: [], watch: [], cats: []}});
    await render(main, params(''));
    expect(main.textContent).toContain('No prices yet');
    expect(main.querySelector('.sub').textContent).toBe('');
    fakeApi({'/api/market': {...MARKET, rows: []}});
    await render(main, params('q=zzz'));
    expect(main.textContent).toContain('No items match.');
    await render(main, params('view=rising'));
    expect(main.textContent).toContain('Nothing here right now.');
  });

  it('switches views with the tabs, keeping the search', async () => {
    const onRoute = vi.fn();
    addEventListener('ahflip:route', onRoute);
    await render(main, params('view=all'));
    tabs(main)[2].click();
    expect(location.search).toBe('?view=rising');
    main.querySelector('input').value = ' wool ';
    tabs(main)[1].click();
    expect(location.search).toBe('?view=vendor&q=wool');
    expect(onRoute).toHaveBeenCalledTimes(2);
    removeEventListener('ahflip:route', onRoute);
  });

  it('filters by category, keeping it across views', async () => {
    const onRoute = vi.fn();
    addEventListener('ahflip:route', onRoute);
    await render(main, params('cat=Trade Goods/Cloth'));
    expect(fetch.mock.calls[0][0]).toBe('/api/market?view=below&q=&cat=Trade%20Goods%2FCloth');
    const sel = main.querySelector('select');
    expect([...sel.options].map(o => o.textContent)).toEqual(['All categories', 'Recipe', 'Trade Goods', '\u00a0\u00a0Cloth', '\u00a0\u00a0Leather']);
    expect(sel.value).toBe('Trade Goods/Cloth');
    sel.value = 'Trade Goods';
    sel.dispatchEvent(new Event('change'));
    expect(location.search).toBe('?view=below&cat=Trade+Goods');
    tabs(main)[1].click();
    expect(location.search).toBe('?view=vendor&cat=Trade+Goods');
    expect(onRoute).toHaveBeenCalledTimes(2);
    removeEventListener('ahflip:route', onRoute);
    fakeApi({'/api/market': {...MARKET, rows: []}});
    await render(main, params('cat=Recipe'));
    expect(main.textContent).toContain('No items match.');
  });

  it('debounces the search box', async () => {
    vi.useFakeTimers({toFake: ['setTimeout', 'clearTimeout']});
    const onRoute = vi.fn();
    addEventListener('ahflip:route', onRoute);
    await render(main, params(''));
    const input = main.querySelector('input');
    input.value = 'li';
    input.dispatchEvent(new Event('input'));
    input.value = 'lin';
    input.dispatchEvent(new Event('input'));
    vi.advanceTimersByTime(299);
    expect(onRoute).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(onRoute).toHaveBeenCalledTimes(1);
    expect(location.search).toBe('?view=below&q=lin');
    removeEventListener('ahflip:route', onRoute);
  });

  it('opens the item panel on row click and closes it', async () => {
    await render(main, params(''));
    main.querySelector('tbody tr[data-item="1"] td').click();
    await flush();
    expect(location.search).toBe('?view=below&item=1');
    expect(main.querySelector('tr.sel').dataset.item).toBe('1');
    const panel = main.querySelector('aside.panel');
    expect(panel.querySelector('h2').firstChild.textContent).toBe('Linen Cloth');
    expect(panel.querySelector('h2 button').title).toBe('Copy name');
    expect(panel.textContent).toContain('If you flip');
    expect(panel.textContent).toContain('per unit');
    expect(panel.querySelectorAll('circle')).toHaveLength(3);
    expect(panel.querySelector('.trades').textContent).toContain('Bought ×2');
    expect(panel.querySelector('.trades').textContent).toContain('Sold ×1');
    main.querySelector('tbody tr[data-item="3"] td').click(); // panel stays, new item
    await flush();
    expect(panel.isConnected).toBe(true);
    panel.querySelector('button.x').click();
    expect(main.querySelector('aside.panel')).toBeNull();
    expect(main.querySelector('tr.sel')).toBeNull();
    expect(location.search).toBe('?view=below');
  });

  it('opens the item from the URL, also when it is not in the list', async () => {
    await render(main, params('item=3'));
    await flush();
    expect(main.querySelector('tr.sel').dataset.item).toBe('3');
    expect(main.querySelector('aside').textContent).toContain('Vendor snipe');
    await render(main, params('item=99'));
    await flush();
    expect(fetch.mock.calls.at(-1)[0]).toBe('/api/history?item=99');
    expect(main.querySelector('aside h2').firstChild.textContent).toBe('Linen Cloth');
    main.querySelector('aside button.x').click();
    expect(main.querySelector('aside')).toBeNull();
  });
});

describe('showItem', () => {
  beforeEach(() => pageShell());
  afterEach(() => vi.unstubAllGlobals());

  it('handles sparse items: no chart, no trades, no range, no deal', async () => {
    fakeApi({'/api/history': {item: 9, name: null, sell: null, min: null, qty: null, median: null, past: 0,
      points: [[TS, 5, 1, 'api']], trades: [], held: 0}});
    const panel = document.createElement('aside');
    await showItem(panel, {item: 9}, new Set(), () => {});
    expect(panel.querySelector('h2').textContent).toBe('#9');
    expect(panel.textContent).toContain('Chart needs 2+ scans');
    expect(panel.textContent).toContain('None yet.');
    expect(panel.textContent).not.toContain('Range');
    expect(panel.textContent).not.toContain('listed');
  });

  it('shows the API error as a toast', async () => {
    fakeApi({'/api/history': new Error('unknown item')});
    const panel = document.createElement('aside');
    await showItem(panel, {item: 9}, new Set(), () => {});
    expect(toastText()).toBe('unknown item');
    expect(panel.textContent).toBe('Loading…');
  });
});
