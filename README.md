# Quarter feed

Prices and tool rules that Quarter signs and every Quarter gateway can pull once a day.

- `body.json` is the feed as written. `feed.json` is the same body, signed. Gateways read only `feed.json`.
- A feed rule can only ask a person before a tool call runs. It never refuses one, and the customer's own rules and prices always come first.
- A gateway takes a feed only if it verifies against the key it was given and is newer than the one it holds.

## For a gateway

```
QUARTER_FEED=https://quarterso.github.io/feed/feed.json
QUARTER_FEED_KEY=ed25519-pub:<the key below>
```

Verify key: not published yet.

## To publish a new version

1. Edit `body.json` and raise `version` by one.
2. Run `./sign.sh`. It asks for the feed signing key and never stores it.
3. Commit `body.json` and `feed.json` together, and push.
