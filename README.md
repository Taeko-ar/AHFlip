# ahflip

Auction house flipping helper for WoW Forever (Classic+). Shows which items are listed below their usual price or below vendor price, tracks your trades, and puts it all on a local website.

- **Website** (`http://localhost:8000`): market overview with price history, watchlist, trade ledger with profit per item and per day, settings. Dark theme.
- **AHFlip addon** (`_addon_/AHFlip`): one-click full auction house scan, and logs your AH buys, sold auctions and vendor sales to the ledger.
- **Blizzard API** (optional): background snapshots between your scans. They lag the game by hours, so in-game scans are the main source.

Python 3.11+, standard library only: nothing to install besides Python.

## Setup (Windows)

1. Install Python from https://www.python.org/downloads/ (tick "Add python.exe to PATH").
2. Download this project (Code › Download ZIP, or `git clone`) and unzip it anywhere.
3. Copy the `_addon_\AHFlip` folder into `World of Warcraft\_forever_\Interface\AddOns\` and restart the game. It shows under "Auctions" in the AddOns list.
4. In the project folder, open a terminal (right-click › Open in Terminal) and run:
   ```
   python ah.py web
   ```
5. Open http://localhost:8000. The first page asks your faction and ruleset and shows whether your WoW folder was found.
6. In game, open the auction house, click **AHFlip scan** above its window, wait for "Reload to save" and click it. The website shows the prices within a few seconds.

From WSL or Linux use `python3` instead of `python`; the WoW folder is found on any Windows drive.

### Optional: Blizzard API snapshots

Create a client at https://develop.battle.net (any name, redirect URL `http://localhost`) and save its id and secret in a file named `.env` next to `ah.py`:
```
BNET_CLIENT_ID=...
BNET_CLIENT_SECRET=...
```
Restart `ah.py web`. Without the file the site runs on in-game scans only. The API part is US only for now (`REGION` in `ahflip/config.py`).

## Use

In game: **AHFlip scan** above the auction house window (once per 15 min), then **Reload to save**. Your trades are imported on every `/reload` or logout. Addon options: `/ahflip settings` or the minimap button.

```
python ah.py web        # website on http://localhost:8000
python ah.py -h         # other commands (snap, import, deals, probe)
python ah.py test       # tests
```

## Development

Dev tools only, the app needs none: Python via [uv](https://docs.astral.sh/uv/) (ruff, pytest + coverage, vulture), JS via pnpm (ESLint, Vitest + coverage, Knip), Lua via luacheck.

```
uv sync && pnpm install   # once
./check.sh                # lint, format check, tests with 100% coverage, dead code, addon lint
```

## Layout

- `ah.py`: entry point. Code in `ahflip/` (module map in `ahflip/__init__.py`), tests in `tests/`.
- `ahflip/web/`: HTTP server, JSON API, and the site (`static/`, one JS module per page).
- `_addon_/AHFlip/`: the WoW addon (Lua).
- `ah.db`: local SQLite database (not in git).
