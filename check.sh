#!/usr/bin/env bash
# All checks: lint, format, tests with coverage, dead code. Python via uv, JS via pnpm.
# First time: uv sync && pnpm install
set -euo pipefail
cd "$(dirname "$0")"

echo "== python: lint and format"
uv run ruff check .
uv run ruff format --check .
echo "== python: tests + coverage"
uv run pytest --cov --cov-report=term
echo "== python: dead code"
uv run vulture

echo "== js: lint"
pnpm -s lint
echo "== js: tests + coverage"
pnpm -s coverage
echo "== js: dead code"
pnpm -s knip

echo "== lua: addon lint (luacheck: sudo apt install lua-check)"
luacheck _addon_

echo "all checks passed"
