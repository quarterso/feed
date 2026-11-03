# Quarter feed

Prices and tool rules that Quarter signs and every Quarter gateway can pull once a day.

- `body.json` is the feed as written. `feed.json` is the same body, signed. Gateways read only `feed.json`.
- A feed rule can only ask a person before a tool call runs. It never refuses one, and the customer's own rules and prices always come first.
- `FORMAT.md` is the open format, for anyone to implement.
- A gateway takes a feed only if it verifies against the key it was given and is newer than the one it holds.

## Quarter guard, for Claude Code

`guard.py` asks you before Claude Code runs a command these rules cover. It never refuses, works offline with the rules built in, and picks up newer signed rules once a day. One file, Python standard library only.

```
curl -fsSLO https://quarterso.github.io/feed/guard.py
python3 guard.py --settings
```

Add the printed `hooks` to `~/.claude/settings.json`, or to managed settings so every machine in a company has it.

## For a gateway

```
QUARTER_FEED=https://quarterso.github.io/feed/feed.json
QUARTER_FEED_KEY=ed25519-pub:<the key below>
```

Verify key: not published yet.

## To publish a new version

1. Edit `body.json` and raise `version` by one, and copy the rules into `BUILT_IN` in `guard.py` (`test_guard.py` checks they match).
2. Run `./sign.sh`. It asks for the feed signing key and never stores it.
3. Commit `body.json` and `feed.json` together, and push.
