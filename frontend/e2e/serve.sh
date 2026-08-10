#!/usr/bin/env bash
# Serve the static export under the /vanta base path, exactly like Pages does.
# Requires `npm run build:static` to have produced out/ first.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d out ] || { echo "out/ missing — run: npm run build:static" >&2; exit 1; }
rm -rf .e2e-root && mkdir .e2e-root
ln -s "$PWD/out" .e2e-root/vanta
exec python3 -m http.server 4173 --bind 127.0.0.1 --directory .e2e-root
