import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render} from '../../ahflip/web/static/js/pages/setup.js';
import {fakeApi, flush, pageShell, posted, toastText} from './helpers.js';

const SETUP = {done: false, detected: {}, faction: 'horde', rs: 2,
  rulesets: {1: 'PvP', 2: 'Normal', 3: 'Roleplay', 15: 'Roleplay PvP'},
  wow: null, addons: '/wow/Interface/AddOns', files: {'AHFlip scan': '/wow/AHFlip.lua', 'Auctionator': null}, api: false};

describe('setup page', () => {
  let main, fetch;
  const text = () => main.textContent;
  const sides = () => [...main.querySelectorAll('.seg button')];
  const saveBtn = () => main.querySelector('.btn.primary');
  async function open(data = {}) {
    fetch = fakeApi({'/api/setup': (_, b) => b ? {ok: true} : {...SETUP, ...data}});
    await render(main);
  }

  beforeEach(() => { main = pageShell(); history.replaceState(null, '', '/setup'); });
  afterEach(() => vi.unstubAllGlobals());

  it('first run: welcome, saved defaults, nothing detected, no WoW, no API keys', async () => {
    await open();
    expect(main.querySelector('h1').textContent).toBe('Welcome to ahflip');
    expect(saveBtn().textContent).toBe('Start');
    expect(sides().map(b => [b.textContent, b.className, b.getAttribute('aria-pressed')]))
      .toEqual([['Horde', 'on', 'true'], ['Alliance', '', 'false']]);
    expect(main.querySelector('#setup-rs').value).toBe('2');
    expect(text()).not.toContain('Filled in from your last AHFlip scan');
    expect(text()).toContain('WoW Forever wasn\'t found');
    expect(text()).toContain('/wow/Interface/AddOns');
    expect([...main.querySelectorAll('.dot')].map(d => d.className)).toEqual(['dot ok', 'dot no']);
    expect(text()).toContain('not found yet');
    expect(text()).toContain('No API keys');
    expect(text()).toContain('BNET_CLIENT_ID=...');
  });

  it('done: prefers the values detected from the last scan, WoW found, API keys found', async () => {
    await open({done: true, detected: {faction: 'alliance', rs: 15}, wow: '/games/wow', api: true});
    expect(main.querySelector('h1').textContent).toBe('Setup');
    expect(saveBtn().textContent).toBe('Save');
    expect(sides().find(b => b.className === 'on').textContent).toBe('Alliance');
    expect(main.querySelector('#setup-rs').value).toBe('15');
    expect(text()).toContain('Filled in from your last AHFlip scan.');
    expect(text()).toContain('Found WoW Forever in /games/wow.');
    expect(text()).toContain('API keys found');
    expect(text()).not.toContain('BNET_CLIENT_ID');
  });

  it('notes a detected ruleset alone too', async () => {
    await open({detected: {rs: 1}});
    expect(main.querySelector('#setup-rs').value).toBe('1');
    expect(sides().find(b => b.className === 'on').textContent).toBe('Horde');
    expect(text()).toContain('Filled in from your last AHFlip scan.');
  });

  it('toggles the faction and saves, then opens Market', async () => {
    await open();
    sides()[1].click();
    expect(sides().map(b => b.className)).toEqual(['', 'on']);
    main.querySelector('#setup-rs').value = '3';
    saveBtn().click(); await flush();
    expect(posted(fetch, '/api/setup')).toEqual({rs: 3, faction: 'alliance'});
    expect(location.pathname).toBe('/market');
  });

  it('shows the error and stays when saving fails', async () => {
    await open();
    fakeApi({'/api/setup': new Error('bad ruleset')});
    saveBtn().click(); await flush();
    expect(toastText()).toBe('bad ruleset');
    expect(location.pathname).toBe('/setup');
  });
});
