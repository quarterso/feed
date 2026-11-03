#!/bin/sh
# Signs body.json into feed.json. Needs the ledger checkout beside this one.
# The key lives in the macOS Keychain as "quarter-feed-signing-key". The first run makes it
# there; it is never printed or written to a file. Elsewhere, the key is asked for.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
item=quarter-feed-signing-key

if command -v security >/dev/null 2>&1; then
  if ! key=$(security find-generic-password -s "$item" -w 2>/dev/null); then
    key="ed25519:$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    security add-generic-password -s "$item" -a quarter -w "$key"
    echo "Made a new feed signing key in the Keychain ($item). Keep it: losing it means every gateway needs a new verify key." >&2
  fi
else
  printf 'feed signing key: ' >&2
  stty -echo; read -r key; stty echo; echo >&2
fi

QUARTER_FEED_SIGNING_KEY=$key uv run --project "$here/../ledger" \
  quarter-ledger --db :memory: feed-sign "$here/body.json" > "$here/feed.json.tmp" 2> "$here/verify-key.tmp" \
  || { cat "$here/verify-key.tmp" >&2; rm -f "$here/verify-key.tmp"; exit 1; }
mv "$here/feed.json.tmp" "$here/feed.json"
sed -n 's/^verify key: //p' "$here/verify-key.tmp" > "$here/verify-key.txt"
rm -f "$here/verify-key.tmp"
echo "Signed feed.json. The public verify key is in verify-key.txt." >&2
