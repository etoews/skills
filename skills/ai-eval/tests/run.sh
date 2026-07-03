#!/usr/bin/env bash
# Unit tests: loader, effort mapping, offline stubs, config. No Docker, no key.
set -euo pipefail
cd "$(dirname "$0")/.."
exec uv run pytest -q "$@"
