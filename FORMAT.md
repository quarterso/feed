# Quarter feed format, version 1

Anyone may publish, read or implement this format. Quarter gateways and `guard.py` read it.

## Envelope

```json
{"feed": { ...body... }, "signature": "<hex>"}
```

`signature` is an Ed25519 signature (RFC 8032) over the body's canonical JSON: keys sorted, no spaces (`json.dumps(body, sort_keys=True, separators=(",", ":"))`). Readers pin the publisher's public key, written `ed25519-pub:<64 hex>`, and ignore any feed that does not verify.

## Body

| Field | Meaning |
|---|---|
| `version` | Whole number from 1. A reader takes a feed only if it is newer than the one it holds. |
| `issued` | Date, `YYYY-MM-DD`. |
| `prices` | `{vendor: {model: {"input_per_million": "3", "output_per_million": "15", ...}}}` in USD. May be empty. |
| `rules` | List of tool rules, below. |

## Tool rule

| Field | Meaning |
|---|---|
| `tool` | Tool name to match, a glob (`*` matches any), case-insensitive. |
| `command` | Optional regular expression, searched case-insensitively in every string of the tool call's input, joined by spaces. |
| `action` | Always `approve`: a person is asked before the call runs. |
| `why` | What the rule catches, in plain words, shown to the person asked. |

## Rules for readers

1. A feed can only ask. A reader never refuses a call because of a feed.
2. The reader's own settings come first. Feed prices fill in models the reader has not priced; feed rules come after the reader's own rules.
3. Keep the last good feed, so a reader that starts offline still has it.
4. Record which feed version was in force, so a later review can show it.
