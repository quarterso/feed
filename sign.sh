#!/bin/sh
# Signs body.json into feed.json. Needs the ledger checkout beside this one.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
printf 'feed signing key: ' >&2
stty -echo; read -r key; stty echo; echo >&2
QUARTER_FEED_SIGNING_KEY=$key uv run --project "$here/../ledger" \
  quarter-ledger --db :memory: feed-sign "$here/body.json" > "$here/feed.json.tmp"
mv "$here/feed.json.tmp" "$here/feed.json"
