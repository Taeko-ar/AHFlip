import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {ago, api, copyName, go, gold, goldText, h, label, link, pct, signed, star, table, toast, when} from '../../ahflip/web/static/js/core.js';
import {fakeApi, flush, pageShell, posted, toastText} from './helpers.js';
import {lineChart, barChart} from '../../ahflip/web/static/js/charts.js';

describe('goldText', () => {
  it('formats copper as gold, silver and copper', () => {
    expect(goldText(12005)).toBe('1g 20s 05c');
    expect(goldText(4500)).toBe('45s 00c');
    expect(goldText(45)).toBe('45c');
    expect(goldText(-250)).toBe('-2s 50c');
  });
  it('shows a dash for unknown values', () => {
    expect(goldText(null)).toBe('–');
  });
});

describe('ago', () => {
  afterEach(() => vi.restoreAllMocks());
  it('says how long ago', () => {
    vi.spyOn(Date, 'now').mockReturnValue(1_000_000_000_000);
    const now = 1_000_000_000;
    expect(ago(now - 10)).toBe('just now');
    expect(ago(now - 600)).toBe('10 min ago');
    expect(ago(now - 7200)).toBe('2 h ago');
    expect(ago(now - 3 * 86400)).toBe('3 days ago');
    expect(ago(null)).toBe('never');
  });
});

describe('label', () => {
  it('uses the name, else the item id', () => {
    expect(label({item: 7, name: 'Linen Cloth'})).toBe('Linen Cloth');
    expect(label({item: 7})).toBe('#7');
  });
});

describe('table', () => {
  const rows = [{item: 1, name: 'b', v: 2}, {item: 2, name: 'A', v: 5}];
  const cols = [{k: 'name', label: 'Item'}, {k: 'v', label: 'V', num: 1}];
  const order = el => [...el.querySelectorAll('tbody tr')].map(tr => tr.dataset.item);

  it('sorts by the given key, biggest first', () => {
    expect(order(table(cols, rows, 'v'))).toEqual(['2', '1']);
  });
  it('re-sorts on header clicks, names case-insensitive', () => {
    const el = table(cols, rows, 'v');
    el.querySelectorAll('th')[0].click(); // name, A to Z
    expect(order(el)).toEqual(['2', '1']);
    el.querySelectorAll('th')[0].click(); // name, Z to A
    expect(order(el)).toEqual(['1', '2']);
  });
  it('calls onRow for row clicks but not for buttons inside the row', () => {
    const onRow = vi.fn();
    const el = table([...cols, {k: 'x', label: '', fmt: () => Object.assign(document.createElement('button'), {textContent: 'b'})}],
      rows, 'v', -1, {onRow, selected: r => r.item === 1});
    el.querySelector('tbody td').click();
    expect(onRow).toHaveBeenCalledWith(rows[1]);
    el.querySelector('tbody button').click();
    expect(onRow).toHaveBeenCalledTimes(1);
    expect(el.querySelector('tr.sel').dataset.item).toBe('1');
  });
});

describe('charts', () => {
  it('draws one dot per point and one bar per value', () => {
    const line = lineChart([{x: 1, y: 10}, {x: 2, y: -5}, {x: 3, y: 20}], {ref: 12, refLabel: 'usual'});
    expect(line.querySelectorAll('circle')).toHaveLength(3);
    const bars = barChart([{label: 'a', bars: [{v: 1, color: 'red'}, {v: 3, color: 'green'}]}]);
    expect(bars.querySelectorAll('rect')).toHaveLength(2);
  });
  it('handles one point, all-zero values, titles, labels and empty bars', () => {
    const line = lineChart([{x: 5, y: 0, title: 'p', color: 'red'}], {ref: 3, xLabel: x => 'x' + x});
    expect(line.querySelector('circle title').textContent).toBe('p');
    expect(line.textContent).toContain('x5');
    expect(line.textContent).toContain(' 3c');
    expect(lineChart([{x: 1, y: 0}, {x: 2, y: 0}]).querySelectorAll('circle')).toHaveLength(2);
    const rows = Array.from({length: 12}, (_, i) => ({label: 'd' + i, bars: [{v: 0, color: 'red', title: 't' + i}]}));
    const bars = barChart(rows);
    expect(bars.querySelectorAll('rect title')).toHaveLength(12);
    expect([...bars.querySelectorAll('text')].filter(t => t.textContent.startsWith('d'))).toHaveLength(6);
    expect(barChart([]).querySelectorAll('rect')).toHaveLength(0);
    // a point without a value: the scale falls back instead of dividing by NaN
    expect(lineChart([{x: 1}, {x: 2, y: 5}]).querySelectorAll('circle')).toHaveLength(2);
  });
});

describe('h', () => {
  it('sets class, attributes and listeners, and skips empty props and kids', () => {
    const fn = vi.fn();
    const e = h('button', {class: 'c', onclick: fn, title: 't', hidden: true, disabled: false, x: null}, 'a', null, false, [1, h('i')]);
    expect(e.className).toBe('c');
    expect(e.getAttribute('title')).toBe('t');
    expect(e.getAttribute('hidden')).toBe('');
    expect(e.hasAttribute('disabled')).toBe(false);
    expect(e.hasAttribute('x')).toBe(false);
    expect(e.innerHTML).toBe('a1<i></i>');
    e.click();
    expect(fn).toHaveBeenCalled();
    expect(h('p').outerHTML).toBe('<p></p>');
  });
});

describe('gold helpers', () => {
  it('formats whole gold, signed values and dates', () => {
    expect(goldText(20000)).toBe('2g 00s 00c');
    expect(gold(5).className).toBe('money');
    expect(signed(5).className).toBe('good');
    expect(signed(-5).className).toBe('bad');
    expect(signed(0).className).toBe('');
    expect(when(null)).toBe('never');
    expect(when(1_700_000_000)).not.toBe('never');
  });
  it('pct compares a price to the usual one', () => {
    expect(pct(null, 5).textContent).toBe('–');
    expect(pct(5, 0).textContent).toBe('–');
    expect(pct(50, 100).className).toBe('good');
    expect(pct(150, 100).textContent).toBe('50%');
    expect(pct(150, 100).className).toBe('bad');
    expect(pct(100, 100).className).toBe('');
  });
});

describe('toast', () => {
  beforeEach(() => { pageShell(); vi.useFakeTimers(); });
  afterEach(() => vi.useRealTimers());
  it('shows a message and hides it after 5 s', () => {
    toast('hi', true);
    const t = document.getElementById('toast');
    expect([t.textContent, t.className, t.style.display]).toEqual(['hi', 'ok', 'block']);
    toast('err');
    expect(t.className).toBe('');
    vi.advanceTimersByTime(5000);
    expect(t.style.display).toBe('none');
  });
});

describe('api', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('GETs, POSTs JSON and throws the server error', async () => {
    const fetch = fakeApi({'/api/a': {x: 1}, '/api/bad': new Error('nope')});
    expect(await api('/api/a')).toEqual({x: 1});
    expect(fetch.mock.calls[0][1]).toEqual({});
    await api('/api/a', {y: 2});
    expect(posted(fetch, '/api/a')).toEqual({y: 2});
    await expect(api('/api/bad')).rejects.toThrow('nope');
    await expect(api('/api/missing')).rejects.toThrow('HTTP 404');
  });
});

describe('go and link', () => {
  it('pushes the URL once and fires the route event', () => {
    const onRoute = vi.fn();
    addEventListener('ahflip:route', onRoute);
    const push = vi.spyOn(history, 'pushState');
    go('/watch');
    go('/watch');
    expect(push).toHaveBeenCalledTimes(1);
    expect(location.pathname).toBe('/watch');
    expect(onRoute).toHaveBeenCalledTimes(2);
    const a = link('/ledger', 'L');
    a.dispatchEvent(new MouseEvent('click', {ctrlKey: true, cancelable: true}));
    expect(location.pathname).toBe('/watch');
    a.dispatchEvent(new MouseEvent('click', {cancelable: true}));
    expect(location.pathname).toBe('/ledger');
    removeEventListener('ahflip:route', onRoute);
    push.mockRestore();
  });
});

describe('table extras', () => {
  it('sorts missing values last, shows tips and blank cells, and has no click without onRow', () => {
    const el = table([{k: 'name', label: 'Item'}, {k: 'v', label: 'V', num: 1, tip: 'value'}, {k: 'w', label: 'W'}],
      [{name: 'a', v: null}, {item: 2, name: 'b', v: 3}, {item: 3, name: 'c', v: 3}], 'name');
    expect(el.querySelectorAll('th')[1].title).toBe('value');
    const ths = el.querySelectorAll('th');
    ths[1].click(); // new numeric key: biggest first
    expect([...el.querySelectorAll('tbody tr')].map(tr => tr.dataset.item ?? '-')).toEqual(['2', '3', '-']);
    ths[2].click(); // new text key: A to Z
    const tr = el.querySelector('tbody tr');
    expect(tr.hasAttribute('class')).toBe(false); // no onRow, nothing selected: no class at all
    expect(tr.children[2].textContent).toBe('');
  });
});

describe('copyName', () => {
  beforeEach(() => pageShell());
  afterEach(() => vi.unstubAllGlobals());
  it('copies the name, shows errors, and is absent without a name', async () => {
    const writeText = vi.fn(async () => {});
    vi.stubGlobal('navigator', {clipboard: {writeText}});
    copyName('Linen Cloth').click(); await flush();
    expect(writeText).toHaveBeenCalledWith('Linen Cloth');
    expect(toastText()).toBe('Copied "Linen Cloth"');
    writeText.mockRejectedValueOnce(new Error('denied'));
    copyName('Silk').click(); await flush();
    expect(toastText()).toBe('denied');
    expect(copyName(null)).toBeNull();
  });
});

describe('star', () => {
  beforeEach(() => pageShell());
  afterEach(() => vi.unstubAllGlobals());
  it('toggles the watchlist and shows errors', async () => {
    const fetch = fakeApi({'/api/watch': (_, b) => b});
    const b = star(7, false);
    b.click(); await flush();
    expect([b.textContent, b.className]).toEqual(['★', 'star on']);
    expect(posted(fetch, '/api/watch')).toEqual({item: 7, on: true});
    b.click(); await flush();
    expect([b.textContent, b.className]).toEqual(['☆', 'star']);
    fakeApi({'/api/watch': new Error('down')});
    b.click(); await flush();
    expect(toastText()).toBe('down');
    expect(star(8, true).textContent).toBe('★');
  });
});
