#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv venv --python 3.11
uv pip sync requirements.lock
uv pip install --no-deps --no-build-isolation -e .
