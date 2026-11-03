# Quarter feed format, version 2

Anyone may publish, read or implement this format. Quarter gateways and `guard.py` read it.

Version 2 adds HTTP rules, for agents that act on an API directly rather than through a shell. A version 1 reader takes a version 2 feed and ignores what it does not know, so the new fields sit beside the old ones and the old ones keep their meaning.

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
| `about` | Version 2. Optional. One item per tool rule: `{"rule": n, "id", "service", "source"}`, where `n` counts `rules` from 1. Readers may show it; it never changes a match. |
| `http` | Version 2. Optional. List of HTTP rules, below. |

## Tool rule

| Field | Meaning |
|---|---|
| `tool` | Tool name to match, a glob (`*` matches any), case-insensitive. |
| `command` | Optional regular expression, searched case-insensitively in every string of the tool call's input, joined by spaces. |
| `action` | Always `approve`: a person is asked before the call runs. |
| `why` | What the rule catches, in plain words, shown to the person asked. |

A tool rule has only these four fields, so that a version 1 reader that refuses unknown fields still takes the feed. Where a tool rule comes from is in `about`.

## HTTP rule

A call matches when every field the rule has matches it.

| Field | Meaning |
|---|---|
| `id` | Short name, unique in the feed, such as `railway.volume`. Readers show it with `why`. |
| `service` | Who runs the API, in words. Not matched. |
| `host` | A glob or a list of globs on the host name the call goes to, without the port, case-insensitive. `*` matches any host. |
| `method` | A list of HTTP methods, or `["*"]` for any. |
| `path` | Regular expression, searched case-insensitively in the path, after percent-decoding, without the query string. Rules anchor it with `^` and `$`. |
| `query` | Optional regular expression, searched case-insensitively in the raw query string. |
| `body` | Optional regular expression, searched case-insensitively in the request body as text. |
| `graphql` | Optional list of globs on GraphQL root field names, case-insensitive. Matches when any root field the call runs matches one of them. Readers find root fields in the query, not in `operationName`, which the client picks. |
| `action` | Always `approve`. |
| `why` | What the rule catches, in plain words. |
| `source` | The public API documentation the rule is drawn from. Not matched. |

A reader that cannot read the body of a call that a `graphql` rule would otherwise match (a multipart upload, say) asks a person.

## Rules for readers

1. A feed can only ask. A reader never refuses a call because of a feed.
2. The reader's own settings come first. Feed prices fill in models the reader has not priced; feed rules come after the reader's own rules, so a reader's own rule that allows a call stands.
3. Keep the last good feed, so a reader that starts offline still has it.
4. Record which feed version was in force, so a later review can show it.
5. Ignore body fields you do not know. Skip an HTTP rule with a field you do not know, since that field may narrow what it matches. A reader that sees only tool calls, such as `guard.py`, ignores `http`.
