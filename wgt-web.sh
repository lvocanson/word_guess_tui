#!/usr/bin/env bash
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO"

rustup target list --installed | grep -qx wasm32-unknown-unknown || rustup target add wasm32-unknown-unknown
cargo build --release --target wasm32-unknown-unknown "$@"

WASM=target/wasm32-unknown-unknown/release/word_guess_tui.wasm
OUT=target/web/word_guess.html
mkdir -p target/web
base64 -w0 "$WASM" > target/web/wasm.b64
sed -e '/^__WASM_BASE64__$/{r target/web/wasm.b64' -e 'd}' web/index.html > "$OUT"
rm target/web/wasm.b64

printf '\033[1;36m%s — %s bytes (wasm %s bytes)\033[0m\n' "$OUT" "$(wc -c < "$OUT")" "$(wc -c < "$WASM")"
