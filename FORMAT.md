# Quarter feed format, version 4

Anyone may publish, read or implement this format. Quarter gateways and `guard.py` read it.

Version 2 adds HTTP rules, for agents that act on an API directly rather than through a shell. Version 3 adds MCP ratings, Quarter's own rating of the tools of known MCP servers. Version 4 adds payees: who an agent may be about to pay, and what they usually charge. An older reader takes a newer feed and ignores what it does not know, so the new fields sit beside the old ones and the old ones keep their meaning.

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
| `mcp` | Version 3. Optional. List of MCP servers and Quarter's ratings of their tools, below. |
| `payees` | Version 4. Optional. List of payees an agent may pay, below. |

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

## MCP rating

An MCP server labels its own tools with `readOnlyHint` and `destructiveHint`. The MCP specification says a client must not trust those hints from a server it does not trust. An MCP rating is an outside rating of the same tools, by tool name.

Each item in `mcp` is one server:

| Field | Meaning |
|---|---|
| `server` | Short name, unique in the feed, such as `github`. |
| `service` | Who runs the server, in words. Not matched. |
| `package` | List of the package names, repositories or addresses the server is installed from. Not matched. |
| `names` | A glob or a list of globs on the server's name as the client shows it, case-insensitive. The user picks that name, so the globs cover the usual ones. |
| `source` | The published tool list the ratings are drawn from. Not matched. |
| `tools` | List of tool ratings, below. |

Each tool rating:

| Field | Meaning |
|---|---|
| `tool` | The tool's exact name, as the server lists it. Matched case-insensitively. |
| `rating` | `ask`: destructive or cannot be undone, such as a delete, a payment, a refund, a message to customers, or a key revoked or rotated. A person is asked before the call runs. `watch`: a write that can be undone. Readers may record it; it never asks. |
| `why` | What the tool does that earns the rating, in plain words, shown to the person asked. |
| `input` | Optional regular expression, searched case-insensitively in the call's input written as canonical JSON (keys sorted, no spaces). The rating applies only when it matches. It narrows a tool that does many things, such as one that runs any API call. |
| `source` | Optional. The page for this tool, where it is not the server's `source`. |

Tools that only read have no rating. A call matches a rating when its tool name is the rating's `tool` and its server name matches one of `names`. Claude Code shows an MCP tool as `mcp__<server>__<tool>`, with every character other than letters, digits, `_` and `-` written as `_`; readers compare names written the same way. A reader that is not sure which server a call goes to says nothing.

## Payee

A payee entry says what is publicly known about someone an agent may pay, such as the seller behind an x402 endpoint. It is the buyer's side: is it safe for my agent to pay this, and is the price normal.

| Field | Meaning |
|---|---|
| `id` | Short name, unique in the feed, such as `x402.exa`. |
| `service` | Who is paid, in words. Not matched. |
| `pay_to` | Optional. List of `{"address", "network"}`: an x402 `payTo` address and its CAIP-2 network, such as `eip155:8453` for Base. Addresses that start with `0x` compare case-insensitively, others exactly. |
| `hosts` | Optional. A glob or a list of globs on the host of the resource paid for, without the port, case-insensitive. |
| `status` | `known` or `caution`, below. |
| `prices` | Optional. List of `{"resource", "max_usd"}`: a glob on the resource URL without its query string, and the most it is listed at, in USD as a decimal string. |
| `why` | What is known about the payee, in plain words, shown to the person asked. |
| `source` | The public page or list the entry is drawn from. Not matched. |

An entry has `pay_to`, `hosts` or both. A payment matches an entry when its `payTo` and network are one item of `pay_to`, or the host of the resource it pays for matches `hosts`. A reader that does not know a payment's network matches the address alone. One operator may run several listed services from one address, so a payment can match more than one entry; each applies.

- `known`: listed in a public directory, such as the x402 Bazaar. Quarter has not vetted it, and a listing can be faked. Nothing asks because a payee is known; the entry carries its prices.
- `caution`: a public report, named in `source`, says paying it has gone wrong. A person is asked before the payment, and shown `why`.

There is no status that refuses a payment. A feed can only ask (rule 1). Payees nobody has listed are not suspect: a reader says nothing about them.

A payment of more than ten times the `max_usd` of a price whose `resource` matches asks a person, whatever the status. A listed price is often the least a metered call costs, so ten times keeps false asks rare, while a quote meant to drain a wallet is far beyond it. A payment no price covers is not checked.

Reports from other companies are not in the feed. Until a report can be disputed, a shared fraud flag only warns, so it never makes a payment wait. Every `caution` entry names a public source, and anyone can dispute one in this repository's issues.

## Rules for readers

1. A feed can only ask. A reader never refuses a call because of a feed.
2. The reader's own settings come first. Feed prices fill in models the reader has not priced; feed rules come after the reader's own rules, so a reader's own rule that allows a call stands.
3. Keep the last good feed, so a reader that starts offline still has it.
4. Record which feed version was in force, so a later review can show it.
5. Ignore body fields you do not know. Skip an HTTP rule, an MCP server, a tool rating or a payee with a field you do not know, since that field may narrow what it matches, and skip a rating or a payee status you do not know. A reader that sees only tool calls ignores `http`, one that sees no MCP calls ignores `mcp`, and one that sees no payments ignores `payees`.
