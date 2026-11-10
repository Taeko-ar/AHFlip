import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {fakeApi, flush, posted, toastText} from './helpers.js';

// Pages are mocked: these tests cover the shell (router, status, theme, houses), not the pages.
const pages = vi.hoisted(() => ({market: vi.fn(), watch: vi.fn(), ledger: vi.fn(), settings: vi.fn(), setup: vi.fn()}));
vi.mock('../../ahflip/web/static/js/pages/market.js', () => ({render: pages.market}));
vi.mock('../../ahflip/web/static/js/pages/watch.js', () => ({render: pages.watch}));
vi.mock('../../ahflip/web/static/js/pages/ledger.js', () => ({render: pages.ledger}));
vi.mock('../../ahflip/web/static/js/pages/settings.js', () => ({render: pages.settings}));
vi.mock('../../ahflip/web/static/js/pages/setup.js', () => ({render: pages.setup}));

const BODY = readFileSync(resolve(import.meta.dirname, '../../ahflip/web/static/index.html'), 'utf8')
  .match(/<body>([\s\S]*)<\/body>/)[1].replace(/<script[\s\S]*?<\/script>/g, '');
const NOW = Math.floor(Date.now() / 1000);
const STATUS = {job: null, error: null, latest: NOW - 600, src: 'api', attempt: NOW - 600, next: NOW + 600,
  scan_ts: null, ledger_n: 5, house: 1, houses: {horde: 1, alliance: 2, goblin: 3}, api: true, setup_done: true};

let status, fetch;
const $ = s => document.querySelector(s);
const statusText = () => [...$('#status').children].map(d => d.textContent);
const houseButtons = () => [...$('#ahSel').children];

// Each boot imports a fresh main.js; drop the listeners and timers the previous one added.
const listeners = [];
async function boot(path = '/') {
  for (const [type, fn] of listeners.splice(0)) globalThis.removeEventListener(type, fn);
  vi.clearAllTimers();
  vi.resetModules();
  const spy = vi.spyOn(globalThis, 'addEventListener');
  document.body.innerHTML = BODY;
  history.replaceState(null, '', path);
  await import('../../ahflip/web/static/js/main.js');
  listeners.push(...spy.mock.calls);
  spy.mockRestore();
  await flush();
}

beforeEach(() => {
  vi.useFakeTimers({toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval']});
  for (const r of Object.values(pages)) r.mockReset();
  status = {...STATUS};
  fetch = fakeApi({
    '/api/status': () => status,
    '/api/snap': {started: true, job: 'snapshot'},
    '/api/settings': (_, b) => ({house: b.house}),
  });
  delete document.documentElement.dataset.theme;
});
afterEach(() => {
  for (const [type, fn] of listeners.splice(0)) globalThis.removeEventListener(type, fn);
  vi.clearAllTimers();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('router', () => {
  it('opens Market for / and unknown paths, and marks the nav link', async () => {
    await boot('/deals');
    expect(pages.market).toHaveBeenCalledTimes(1);
    const [main, params, poll] = pages.market.mock.calls[0];
    expect(main).toBe($('#main'));
    expect(params).toBeInstanceOf(URLSearchParams);
    expect(typeof poll).toBe('function');
    expect(document.title).toBe('Market · ahflip');
    expect([...$('#nav').children].map(a => a.className)).toEqual(['on', '', '', '']);
  });

  it('renders the page for the URL with its query, on popstate and route events', async () => {
    await boot('/ledger?x=1');
    expect(pages.ledger.mock.calls[0][1].get('x')).toBe('1');
    history.pushState(null, '', '/settings');
    dispatchEvent(new PopStateEvent('popstate'));
    await flush();
    expect(pages.settings).toHaveBeenCalledTimes(1);
    expect(document.title).toBe('Settings · ahflip');
    $('#nav a[href="/watch"]').click();
    await flush();
    expect(location.pathname).toBe('/watch');
    expect(pages.watch).toHaveBeenCalledTimes(1);
  });

  it('routes /setup without a nav link', async () => {
    await boot('/setup');
    expect(pages.setup).toHaveBeenCalledTimes(1);
    expect(document.title).toBe('Setup · ahflip');
    expect($('#nav a[href="/setup"]')).toBeNull();
    expect([...$('#nav').children].map(a => a.className)).toEqual(['', '', '', '']);
  });

  it('sends a new install to /setup, but not when already there', async () => {
    status = {...STATUS, setup_done: false};
    await boot('/market');
    expect(location.pathname).toBe('/setup');
    expect(pages.setup).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.setup).toHaveBeenCalledTimes(1);
  });

  it('shows the loading state only for slow pages', async () => {
    await boot('/watch');
    let done;
    pages.watch.mockImplementation(() => new Promise(r => { done = r; }));
    dispatchEvent(new Event('ahflip:route'));
    await flush();
    expect($('#main').classList.contains('busy')).toBe(false);
    vi.advanceTimersByTime(150);
    expect($('#main').classList.contains('busy')).toBe(true);
    expect($('#main').dataset.loading).toBe('Loading…');
    done();
    await flush();
    expect($('#main').classList.contains('busy')).toBe(false);
  });

  it('shows page errors as a toast', async () => {
    pages.market.mockRejectedValue(new Error('HTTP 500'));
    await boot('/market');
    expect(toastText()).toBe('HTTP 500');
    expect($('#main').classList.contains('busy')).toBe(false);
  });
});

describe('status', () => {
  it('shows price source, scan time and the next API check', async () => {
    await boot();
    expect(statusText()).toEqual(['Prices: API, 10 min ago', 'In-game scan never', 'API checked 10 min ago, next in 10 min']);
    expect($('#snapBtn').disabled).toBe(false);
    expect($('#snapBtn').hidden).toBe(false);
  });

  it('shows a running job, errors, unknown sources and no auto refresh', async () => {
    status = {...STATUS, src: 'other', job: 'snapshot', error: 'API down'};
    await boot();
    expect(statusText()).toEqual(['Prices: other, 10 min ago', 'In-game scan never', 'Running: snapshot…', 'API down']);
    expect($('#status .err')).not.toBeNull();
    expect($('#snapBtn').disabled).toBe(true);
    status = {...STATUS, latest: null, job: null, next: null};
    vi.advanceTimersByTime(5000);
    await flush();
    expect(statusText()).toEqual(['No prices yet', 'In-game scan never', 'API checked 10 min ago, auto off']);
  });

  it('says when API keys are missing and hides the snapshot button', async () => {
    status = {...STATUS, api: false};
    await boot();
    expect(statusText()[2]).toBe('API off (no keys): in-game scans only');
    expect($('#snapBtn').hidden).toBe(true);
  });

  it('says when the server is not reachable', async () => {
    fetch.mockRejectedValue(new TypeError('Failed to fetch'));
    await boot();
    expect(statusText()).toEqual(['Server not reachable. Is `ah.py web` running?']);
  });

  it('re-renders Market and Watch on new prices, Ledger on new trades', async () => {
    await boot('/market');
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.market).toHaveBeenCalledTimes(1); // nothing new
    status = {...STATUS, latest: NOW};
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.market).toHaveBeenCalledTimes(2);

    await boot('/ledger');
    status = {...STATUS, latest: NOW + 1}; // new prices: the ledger does not show them
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.ledger).toHaveBeenCalledTimes(1);
    status = {...status, ledger_n: 6};
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.ledger).toHaveBeenCalledTimes(2);

    await boot('/watch');
    status = {...status, latest: NOW + 2};
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.watch).toHaveBeenCalledTimes(2);

    await boot('/settings');
    status = {...status, latest: NOW + 3, ledger_n: 7};
    vi.advanceTimersByTime(5000); await flush();
    expect(pages.settings).toHaveBeenCalledTimes(1);
  });
});

describe('snapshot button', () => {
  it('starts a snapshot, reports a busy job or an error', async () => {
    await boot();
    $('#snapBtn').click(); await flush();
    expect(posted(fetch, '/api/snap')).toEqual({});
    expect(toastText()).toBe('');
    fakeApi({'/api/snap': {started: false, job: 'retry'}, '/api/status': () => status});
    $('#snapBtn').click(); await flush();
    expect(toastText()).toBe('Busy: retry');
    fakeApi({'/api/snap': new Error('no API key'), '/api/status': () => status});
    $('#snapBtn').click(); await flush();
    expect(toastText()).toBe('no API key');
  });
});

describe('theme', () => {
  it('starts dark and toggles, remembering the choice', async () => {
    const set = vi.spyOn(Storage.prototype, 'setItem');
    await boot();
    expect($('#themeBtn').textContent).toBe('Light theme');
    $('#themeBtn').click();
    expect(document.documentElement.dataset.theme).toBe('light');
    expect($('#themeBtn').textContent).toBe('Dark theme');
    expect(set).toHaveBeenLastCalledWith('theme', 'light');
    $('#themeBtn').click();
    expect(document.documentElement.dataset.theme).toBeUndefined();
    expect(set).toHaveBeenLastCalledWith('theme', 'dark');
  });

  it('keeps the light theme set by index.html, also when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked'); });
    document.documentElement.dataset.theme = 'light';
    await boot();
    expect($('#themeBtn').textContent).toBe('Dark theme');
    expect(document.documentElement.dataset.theme).toBe('light');
  });
});

describe('auction house selector', () => {
  it('marks the current house and ignores clicks on it', async () => {
    await boot();
    expect(houseButtons().map(b => [b.textContent, b.className, b.getAttribute('aria-pressed')]))
      .toEqual([['Horde', 'on', 'true'], ['Alliance', '', 'false'], ['Goblin', '', 'false']]);
    expect(houseButtons()[1].title).toBe('Alliance auction house (#2)');
    houseButtons()[0].click(); await flush();
    expect(posted(fetch, '/api/settings')).toBeUndefined();
  });

  it('switches house: saves it, shows the loading state at once, re-renders', async () => {
    await boot('/market');
    let done;
    pages.market.mockImplementation(() => new Promise(r => { done = r; }));
    houseButtons()[2].click();
    expect(houseButtons()[2].className).toBe('on');
    expect(houseButtons()[0].className).toBe('');
    expect($('#main').classList.contains('busy')).toBe(true);
    expect($('#main').dataset.loading).toBe('Loading the Goblin auction house…');
    await flush();
    expect(posted(fetch, '/api/settings')).toEqual({house: 3});
    vi.advanceTimersByTime(0);
    expect($('#main').dataset.loading).toBe('Loading the Goblin auction house…');
    status = {...STATUS, house: 3, latest: NOW + 5}; // lastTs was reset: no second re-render
    done(); await flush();
    expect(pages.market).toHaveBeenCalledTimes(2);
    expect(houseButtons()[2].className).toBe('on');
  });

  it('shows the error and redraws the houses when the switch fails', async () => {
    await boot();
    fakeApi({'/api/settings': new Error('bad house'), '/api/status': () => status});
    houseButtons()[1].click(); await flush();
    expect(toastText()).toBe('bad house');
    expect($('#main').classList.contains('busy')).toBe(false);
    expect(houseButtons()[0].className).toBe('on');
  });
});
