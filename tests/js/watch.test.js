import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render} from '../../ahflip/web/static/js/pages/watch.js';
import {fakeApi, flush, pageShell} from './helpers.js';

const WATCH = {items: [
  {item: 1, name: 'Linen Cloth', sell: 50, min: 500, qty: 4, median: 1000, past: 6},
  {item: 2, name: null, sell: null, min: null, qty: null, median: null, past: 0},
  {item: 3, name: 'Silk', sell: 10, min: 300, qty: 1, median: 0, past: 1},
]};
const HISTORY = {item: 1, name: 'Linen Cloth', sell: 50, min: 500, qty: 4, median: 1000, past: 6,
  points: [], trades: [], held: 0};

describe('watch page', () => {
  let main;
  beforeEach(() => {
    main = pageShell();
    history.replaceState(null, '', '/watch');
    fakeApi({'/api/watch': WATCH, '/api/history': HISTORY});
  });
  afterEach(() => vi.unstubAllGlobals());

  it('lists watched items sorted by name, with dashes for missing values', async () => {
    await render(main, new URLSearchParams());
    const rows = [...main.querySelectorAll('tbody tr')];
    expect(rows.map(tr => tr.dataset.item)).toEqual(['2', '1', '3']);
    expect(rows[0].textContent).toContain('#2');
    expect(rows[1].textContent).toContain('-50%');
    expect(main.querySelectorAll('.star.on')).toHaveLength(3);
    expect(main.querySelector('aside')).toBeNull();
  });

  it('says how to add items when the list is empty', async () => {
    fakeApi({'/api/watch': {items: []}});
    await render(main, new URLSearchParams());
    expect(main.querySelector('table')).toBeNull();
    expect(main.textContent).toContain('Star items on the Market page');
  });

  it('opens the item panel from a row click or the URL, and closes it', async () => {
    await render(main, new URLSearchParams('item=1'));
    await flush();
    expect(main.querySelector('tr.sel').dataset.item).toBe('1');
    expect(main.querySelector('aside h2').firstChild.textContent).toBe('Linen Cloth');
    main.querySelector('tbody tr[data-item="3"] td').click();
    await flush();
    expect(location.search).toBe('?item=3');
    expect(main.querySelectorAll('aside')).toHaveLength(1);
    main.querySelector('aside button.x').click();
    expect(main.querySelector('aside')).toBeNull();
    expect(location.pathname + location.search).toBe('/watch');
  });
});
