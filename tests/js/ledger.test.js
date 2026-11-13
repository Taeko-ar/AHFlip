import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {fakeApi, flush, pageShell, posted, toastText} from './helpers.js';

const NOW = Math.floor(Date.now() / 1000), DAY = 86400;
const ENTRIES = [ // newest first, like /api/ledger
  {id: 4, ts: NOW - 60, kind: 'sell', item: 1, name: 'Linen Cloth', qty: 4, price: 200, note: 'typo', src: 'addon'},
  {id: 3, ts: NOW - 3 * DAY, kind: 'sell', item: 2, name: null, qty: 2, price: 100, note: null, src: 'addon'},
  {id: 2, ts: NOW - 20 * DAY, kind: 'buy', item: 1, name: 'Linen Cloth', qty: 10, price: 100, note: null, src: 'addon'},
  {id: 1, ts: NOW - 60 * DAY, kind: 'buy', item: 3, name: 'Wool Cloth', qty: 5, price: 10, note: null, src: 'manual'},
];
const LEDGER = {entries: ENTRIES, cut: 0.05, now: {1: {min: 300, sell: 50}, 3: {min: null, sell: 40}}};
const HISTORY = {item: 1, name: 'Linen Cloth', sell: 50, min: 300, qty: 4, median: 280, past: 6, points: [], trades: [], held: 6};

describe('ledger page', () => {
  let main, fetch, render;
  const buttons = (sel = 'button') => [...main.querySelectorAll(sel)];
  const click = name => buttons().find(b => b.textContent === name).click();
  const stat = name => [...main.querySelectorAll('.stat')].find(s => s.firstChild.textContent === name).lastChild.textContent;
  const items = () => [...main.querySelectorAll('tbody tr')].map(tr => tr.dataset.item);

  beforeEach(async () => {
    vi.resetModules(); // the page keeps its filters in module state
    ({render} = await import('../../ahflip/web/static/js/pages/ledger.js'));
    main = pageShell();
    history.replaceState(null, '', '/ledger');
    fetch = fakeApi({'/api/ledger': LEDGER, '/api/watch': {items: [{item: 1}]}, '/api/history': HISTORY});
    await render(main);
  });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('sums all trades into stats, charts and the items table', () => {
    expect(stat('Spent')).toBe('10s 50c');      // 10x100 + 5x10
    expect(stat('Received')).toBe('10s 00c');   // 4x200 + 2x100
    expect(stat('Net')).toBe('-50c');
    expect(stat('Realized')).toBe('4s 00c');    // 4 x (200 - 100); item 2 has no buys
    expect(stat('Stock')).toBe('19s 10c');      // 6 x 285 (AH after cut) + 5 x 40 (vendor)
    expect(stat('Trades')).toBe('4');
    expect(main.querySelectorAll('.charts rect')).toHaveLength(8);
    expect(main.querySelectorAll('.charts circle')).toHaveLength(4);
    expect(items()).toEqual(['2', '3', '1']); // cash net, biggest first
    const rows = [...main.querySelectorAll('tbody tr')];
    expect(rows[0].textContent).toContain('#2');
    expect(rows[1].textContent).toContain('vendor');
    expect(rows[2].textContent).toContain('AH');
  });

  it('filters by period, type and item name', () => {
    click('Today');
    expect(stat('Trades')).toBe('1');
    expect(main.textContent).toContain('Needs 2+ trades.');
    click('7 days');
    expect(stat('Trades')).toBe('2');
    click('30 days');
    click('Buys');
    expect(stat('Trades')).toBe('1');
    expect(buttons('.seg .on').map(b => b.textContent)).toEqual(['30 days', 'Buys']);
    click('All'); click('Sells');
    const q = main.querySelector('input');
    q.value = 'LINEN';
    q.dispatchEvent(new Event('input'));
    expect(stat('Trades')).toBe('1');
    q.value = 'zzz';
    q.dispatchEvent(new Event('input'));
    expect(main.textContent).toContain('No trades match.');
  });

  it('says how to log trades when there are none', async () => {
    fakeApi({'/api/ledger': {entries: [], cut: 0.05, now: {}}, '/api/watch': new Error('down')});
    await render(main);
    await flush();
    expect(main.textContent).toContain('No trades yet.');
  });

  it('shows the days and trades tabs', () => {
    click('Days');
    expect(buttons('.tab.on')[0].textContent).toBe('Days');
    const days = [...main.querySelectorAll('tbody tr')].map(tr => tr.firstChild.textContent);
    expect(days).toHaveLength(4);
    expect([...days].sort().reverse()).toEqual(days); // newest day first
    click('Trades');
    const rows = [...main.querySelectorAll('tbody tr')];
    expect(rows.map(tr => tr.dataset.item)).toEqual(['1', '2', '1', '3']);
    expect(rows[0].textContent).toContain('sold');
    expect(rows[0].textContent).toContain('typo');
    expect(rows[2].textContent).toContain('bought');
    expect(rows[2].querySelector('.bad')).not.toBeNull();
  });

  it('orders days oldest first in the chart even when entries arrive oldest first', async () => {
    fakeApi({'/api/ledger': {...LEDGER, entries: [...ENTRIES].reverse()}, '/api/watch': {items: []}});
    await render(main);
    const days = [...main.querySelectorAll('.charts rect title')].map(t => t.textContent.slice(0, 10)).filter((d, i, a) => a.indexOf(d) === i);
    expect(days).toHaveLength(4);
    expect([...days].sort()).toEqual(days); // YYYY-MM-DD
  });

  it('edits a trade: save, error and cancel', async () => {
    click('Trades');
    const onRoute = vi.fn();
    addEventListener('ahflip:route', onRoute);
    buttons('tbody tr:first-child button')[0].click();
    const form = main.querySelector('form.edit');
    expect(form.textContent).toContain('Sold Linen Cloth');
    const [qty, price, note] = form.querySelectorAll('input');
    expect([qty.value, price.value, note.value]).toEqual(['4', '2s 00c', 'typo']);
    qty.value = '3';
    form.querySelector('button.primary').click();
    await flush();
    expect(posted(fetch, '/api/ledger')).toEqual({edit: 4, kind: 'sell', item: '1', qty: '3', price: '2s 00c', note: 'typo'});
    expect(toastText()).toBe('Saved');
    expect(onRoute).toHaveBeenCalled();
    removeEventListener('ahflip:route', onRoute);

    fakeApi({'/api/ledger': new Error('bad price')});
    buttons('tbody tr:nth-child(3) button')[0].click();
    expect(main.querySelector('form.edit').textContent).toContain('Bought Linen Cloth');
    expect(main.querySelectorAll('form.edit input')[2].value).toBe('');
    main.querySelector('form.edit button.primary').click();
    await flush();
    expect(toastText()).toBe('bad price');
    click('Cancel');
    expect(main.querySelector('form.edit')).toBeNull();
  });

  it('deletes a trade after confirming', async () => {
    click('Trades');
    const confirm = vi.fn(() => false);
    vi.stubGlobal('confirm', confirm);
    const del = () => main.querySelector('tbody tr button[aria-label="Delete"]').click();
    del();
    expect(confirm).toHaveBeenCalledWith('Delete this trade?');
    expect(posted(fetch, '/api/ledger')).toBeUndefined();
    confirm.mockReturnValue(true);
    del(); await flush();
    expect(posted(fetch, '/api/ledger')).toEqual({delete: 4});
    fakeApi({'/api/ledger': new Error('gone')});
    del(); await flush();
    expect(toastText()).toBe('gone');
  });

  it('opens the item panel on row click and closes it', async () => {
    main.querySelector('tbody tr[data-item="1"] td').click();
    await flush();
    expect(main.querySelector('tr.sel').dataset.item).toBe('1');
    expect(main.querySelector('aside h2').firstChild.textContent).toBe('Linen Cloth');
    main.querySelector('tbody tr[data-item="3"] td').click();
    await flush();
    expect(main.querySelectorAll('aside')).toHaveLength(1);
    expect(fetch.mock.calls.at(-1)[0]).toBe('/api/history?item=3');
    main.querySelector('aside button.x').click();
    expect(main.querySelector('aside')).toBeNull();
    expect(main.querySelector('tr.sel')).toBeNull();
  });
});
