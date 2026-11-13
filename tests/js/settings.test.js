import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render} from '../../ahflip/web/static/js/pages/settings.js';
import {fakeApi, flush, pageShell, posted, toastText} from './helpers.js';

const SETTINGS = {flip_discount: 0.65, min_profit: 150, cut: 0.05, cut_goblin: 0.15, hist_days: 14, min_snaps: 3,
  min_listed: 3, max_spread: 10, snap_minutes: 60, rs: 2,
  house: 1, house_horde: 1, house_goblin: 3,
  addon_file: '/wow/AHFlip.lua', scan_file: '/wow/Auctionator.lua', scan_realm: 'Realm_Horde'};
const STATUS = {scan_ts: 1_700_000_000, retried: null, missing: 12,
  scan_files: {'AHFlip.lua': '/wow/AHFlip.lua', 'Auctionator.lua': null}};

describe('settings page', () => {
  let main, poll, fetch;
  const input = k => main.querySelector('#set-' + k);
  const type = (k, v) => { input(k).value = v; input(k).dispatchEvent(new Event('input')); };
  const bar = () => main.querySelector('.savebar');
  const barButton = name => [...bar().querySelectorAll('button')].find(b => b.textContent === name);

  beforeEach(async () => {
    main = pageShell();
    poll = vi.fn();
    fetch = fakeApi({'/api/settings': (_, b) => b ? {...SETTINGS, ...b} : SETTINGS, '/api/status': STATUS, '/api/retry': {started: true, job: 'retry'}});
    await render(main, new URLSearchParams(), poll);
  });
  afterEach(() => vi.unstubAllGlobals());

  it('shows values in their display units and the scan files', () => {
    expect(input('flip_discount').value).toBe('65');
    expect(input('min_profit').value).toBe('1s 50c');
    expect(input('hist_days').value).toBe('14');
    expect(input('addon_file').className).toBe('wide');
    expect(input('hist_days').getAttribute('inputmode')).toBe('decimal');
    expect(input('min_profit').hasAttribute('inputmode')).toBe(false);
    expect(main.querySelectorAll('.dot.ok')).toHaveLength(1);
    expect(main.textContent).toContain('no file found at this path');
    expect(main.textContent).toContain('12 items without info');
    expect(main.textContent).toContain('Last: never');
    expect(bar().hidden).toBe(true);
    expect(main.querySelector('a[href="/setup"]').textContent).toBe('Run setup again');
  });

  it('counts unsaved changes and discards them', () => {
    type('hist_days', '7');
    expect(bar().hidden).toBe(false);
    expect(bar().textContent).toContain('1 unsaved change');
    type('cut', '6');
    expect(bar().textContent).toContain('2 unsaved changes');
    barButton('Discard').click();
    expect(input('hist_days').value).toBe('14');
    expect(input('cut').value).toBe('5');
    expect(bar().hidden).toBe(true);
  });

  it('saves only the changed values, parsed per type', async () => {
    type('flip_discount', '50');
    type('hist_days', '7');
    type('min_profit', ' 2s ');
    type('scan_realm', ' Other ');
    barButton('Save').click();
    await flush();
    expect(posted(fetch, '/api/settings')).toEqual({flip_discount: 0.5, hist_days: 7, min_profit: '2s', scan_realm: 'Other'});
    expect(toastText()).toBe('Saved');
    expect(poll).toHaveBeenCalled();
    expect(bar().hidden).toBe(true);
  });

  it('keeps the changes and shows the error when saving fails', async () => {
    fakeApi({'/api/settings': new Error('hist_days must be at least 1')});
    type('hist_days', '0');
    barButton('Save').click();
    await flush();
    expect(toastText()).toBe('hist_days must be at least 1');
    expect(bar().hidden).toBe(false);
    expect(poll).not.toHaveBeenCalled();
  });

  it('retries item info: started, busy, or failed', async () => {
    const retry = [...main.querySelectorAll('button')].find(b => b.textContent === 'Retry now');
    retry.click(); await flush();
    expect(toastText()).toBe('Retry started');
    expect(document.getElementById('toast').className).toBe('ok');
    fakeApi({'/api/retry': {started: false, job: 'snapshot'}});
    retry.click(); await flush();
    expect(toastText()).toBe('Busy: snapshot');
    expect(poll).toHaveBeenCalledTimes(2);
    fakeApi({'/api/retry': new Error('down')});
    retry.click(); await flush();
    expect(toastText()).toBe('down');
  });
});
