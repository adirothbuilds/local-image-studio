#!/bin/bash
set -euo pipefail
source "$(dirname "$0")/env.sh"
[[ "$(uname -s)" == Darwin && "$(uname -m)" == arm64 ]] || { echo 'Requires an Apple Silicon Mac.'; exit 1; }
mkdir -p .runtime/bin logs outputs
if [[ ! -x .runtime/bin/uv ]]; then
  curl --fail --location --retry 3 https://github.com/astral-sh/uv/releases/download/0.13.5/uv-aarch64-apple-darwin.tar.gz -o "$TMPDIR/uv.tar.gz"
  tar -xzf "$TMPDIR/uv.tar.gz" -C "$TMPDIR"
  cp "$TMPDIR/uv-aarch64-apple-darwin/uv" .runtime/bin/uv
  chmod +x .runtime/bin/uv
fi
uv python install 3.12 --no-bin
if [[ -f uv.lock ]]; then uv sync --locked; else uv sync; fi
uv --version > logs/setup-versions.txt
.venv/bin/python --version >> logs/setup-versions.txt
.venv/bin/python -m studio.config
printf '\nPackages ready. Downloading model next; launch with ./studio.sh run\n'
