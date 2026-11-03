# Quarter feed

Prices and rules that Quarter signs and every Quarter gateway can pull once a day. The rules ask a person before an agent runs a destructive command or makes a destructive API call: 35 for shell commands and 121 for the HTTP APIs of 40 services. `COVERAGE.md` lists them.

The feed also rates the tools of 27 popular MCP servers: 112 tools that delete, pay, send or revoke are rated `ask`, and 461 writes that can be undone are rated `watch`. A server rates its own tools, and the MCP specification says clients must not trust those labels from a server they do not trust. These ratings come from outside. `RATINGS.md` lists them.

- `body.json` is the feed as written. `feed.json` is the same body, signed. Gateways read only `feed.json`.
- A feed rule can only ask a person before a tool call runs. It never refuses one, and the customer's own rules and prices always come first.
- `FORMAT.md` is the open format, for anyone to implement.
- `cases.json` holds, for every rule and every `ask` rating, one call it must catch and one close call it must let through. `python3 -m unittest` checks them.
- A gateway takes a feed only if it verifies against the key it was given and is newer than the one it holds.

## Quarter guard, for Claude Code and Cursor

`guard.py` asks you before a coding agent runs a command or makes an API call these rules cover. It never refuses, works offline with the rules built in, and picks up newer signed rules once a day. One file, Python standard library only.

```
curl -fsSLO https://quarterso.github.io/feed/guard.py
python3 guard.py --settings
```

For Claude Code, add the printed `hooks` to `~/.claude/settings.json`, or to managed settings so every machine in a company has it.

For Cursor, run `python3 guard.py --settings --host cursor` and add the printed hooks to `~/.cursor/hooks.json`, or to the enterprise `hooks.json` for every machine. It uses the `beforeShellExecution` and `beforeMCPExecution` hooks.

What it checks:

- Every shell command, against the shell rules.
- API calls made from the shell with `curl`, `wget`, HTTPie (`http`, `https`, `xh`) or `gh api`, against the HTTP rules. It reads the method, host, path, query and body, follows pipes, `&&` chains, `bash -c` and `$(...)`, and reads a body from a file or a here-document. It reads GraphQL queries to find the mutation a call runs.
- MCP tool calls whose input names a full URL and an HTTP method, against the HTTP rules.
- MCP tool calls to a server Quarter rates, against its `ask` ratings. It knows the server by the tool name and the usual names people give the server, such as `github` or `claude_ai_GitHub`.

What it does not check:

- API calls made from inside a program, such as a Python script or a Node app.
- A URL whose host is in a shell variable. It says nothing then.
- A body in a shell variable or read from a pipe it cannot follow. It says nothing, except for a GraphQL endpoint a rule covers. There it asks, since it cannot tell which mutation runs.
- MCP servers Quarter has not rated, or a rated server under a name the ratings do not expect. It says nothing then.

Other agents:

- OpenAI Codex has a PreToolUse hook with the same input as Claude Code, but it does not act on "ask" yet. It only allows or denies. The guard never refuses, so it has no Codex setup until Codex can ask.
- Gemini CLI hooks can only allow or deny, and Google replaced Gemini CLI with Antigravity CLI in June 2026. The guard has no setup for either yet.

## For a gateway

```
QUARTER_FEED=https://quarterso.github.io/feed/feed.json
QUARTER_FEED_KEY=ed25519-pub:<the key below>
```

Verify key: `ed25519-pub:37115bdfec3099c6a0391470c618d5a12466d10a7148b97451ea87d624183b20`. guard.py has it built in.

## To publish a new version

1. Edit `body.json` and raise `version` by one, and copy the tool rules and the HTTP rules into `BUILT_IN` in `guard.py`, leaving out each HTTP rule's `service`, `source` and `action`. Copy the `ask` ratings into `BUILT_IN["mcp"]` with only `server`, `names`, `tool`, `rating`, `why` and `input` (`test_guard.py` checks they match). Give each new rule an `id` and a `source`, and it and each new `ask` rating its two calls in `cases.json`. Update `COVERAGE.md` and `RATINGS.md`.
2. Run `./sign.sh`. On a Mac it keeps the key in the Keychain and makes it on the first run; elsewhere it asks for the key. It never prints or stores the key in a file.
3. Commit `body.json` and `feed.json` together, and push.

## Licence

The code (`guard.py`, `sign.sh` and the tests) is under the MIT licence in `LICENSE`.

The data (`body.json`, `feed.json`, `cases.json`, and the rules and ratings copied into `guard.py`) is under Creative Commons Attribution 4.0 in `LICENSE-DATA`. You may ship it in your own gateway or product, paid or free. Credit "Quarter feed, quarterfi.com" where you list your sources.
