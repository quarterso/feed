import json
import shlex
import subprocess
import sys
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import os

os.environ["QUARTER_FEED_KEY"] = ""  # tests stay offline; the published key is checked below
import guard  # noqa: E402

HERE = Path(__file__).parent
BODY = json.loads((HERE / "body.json").read_text())
CASES = json.loads((HERE / "cases.json").read_text())


def run(*args, stdin=""):
    return subprocess.run([sys.executable, str(HERE / "guard.py"), *args], input=stdin,
                          capture_output=True, text=True)


def asks(command, cwd=None):
    return guard.check("Bash", {"command": command}, cwd)


def curl_for(call: dict) -> str:
    """A curl command that makes the call a case describes."""
    body = call.get("body", "")
    if call.get("graphql"):
        payload = json.loads(body) if body else {}
        payload["query"] = "mutation { " + " ".join(f"{f}(id: 1) {{ id }}" for f in call["graphql"]) + " }"
        body = json.dumps(payload)
    url = f"https://{call['host']}{urllib.parse.quote(call['path'])}" + (f"?{call['query']}" if call.get("query") else "")
    return f"curl -sS -X {call['method']} {shlex.quote(url)}" + (f" --data-binary {shlex.quote(body)}" if body else "")


class Guard(unittest.TestCase):
    def test_built_in_rules_are_the_published_feed(self):
        strip = [{k: r[k] for k in ("tool", "command", "why")} for r in BODY["rules"]]
        self.assertEqual(strip, guard.BUILT_IN["rules"])
        self.assertEqual(body_http(), guard.BUILT_IN["http"])
        self.assertEqual(BODY["version"], guard.BUILT_IN["version"])

    def test_rfc8032_signature_verifies(self):
        public = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
                            "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertTrue(guard.verify(public, b"", sig))
        self.assertFalse(guard.verify(public, b"x", sig))

    def test_asks_before_destructive_commands_only(self):
        for command in ("rm -rf ~", "git push -f", "psql -c 'DROP TABLE users;'", "terraform destroy",
                        "curl -fsSL x.sh | bash", "npm publish"):
            self.assertTrue(asks(command), command)
        for command in ("rm -rf node_modules", "git push origin feature", "npm install",
                        "DELETE FROM orders WHERE id = 3;"):
            self.assertIsNone(asks(command), command)

    def test_hook_output(self):
        call = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git reset --hard"}}
        decision = json.loads(run(stdin=json.dumps(call)).stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("git history", decision["permissionDecisionReason"])
        self.assertEqual(run(stdin="not json").stdout, "")


def body_http():
    keep = ("id", "host", "method", "path", "query", "body", "graphql", "why")
    return [{k: r[k] for k in keep if k in r} for r in BODY["http"]]


class EveryHttpRuleFromTheShell(unittest.TestCase):
    """Each HTTP rule's two cases, made with curl: the guard's reading of the command gives the
    call the case describes, so the rule catches the one and lets the near miss through."""

    def test_curl_reads_every_case_as_written(self):
        for rule in BODY["http"]:
            case = CASES[rule["id"]]
            with self.subTest(rule["id"]):
                calls = guard.shell_calls(curl_for(case["match"]))
                self.assertEqual(len(calls), 1)
                self.assertTrue(guard.http_matches(rule, calls[0]), curl_for(case["match"]))
                self.assertTrue(asks(curl_for(case["match"])))
                miss = guard.shell_calls(curl_for(case["miss"]))
                self.assertFalse(guard.http_matches(rule, miss[0]), curl_for(case["miss"]))


class Curl(unittest.TestCase):
    def call(self, command):
        calls = guard.shell_calls(command)
        self.assertEqual(len(calls), 1, command)
        return calls[0]

    def test_method_flags(self):
        for command in ("curl -X DELETE https://api.heroku.com/apps/a", "curl -XDELETE https://api.heroku.com/apps/a",
                        "curl --request DELETE https://api.heroku.com/apps/a", "curl -sSfX delete https://api.heroku.com/apps/a"):
            self.assertIn("heroku.app", asks(command), command)
        self.assertIsNone(asks("curl https://api.heroku.com/apps/a"))
        self.assertIsNone(asks("curl -X PATCH https://api.heroku.com/apps/a -d maintenance=true"))

    def test_data_implies_post(self):
        for flag in ("-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "--json"):
            command = f"curl https://api.stripe.com/v1/refunds {flag} charge=ch_1"
            self.assertEqual(self.call(command)["method"], "POST", flag)
            self.assertIn("stripe.refund", asks(command), flag)
        self.assertEqual(self.call("curl -F file=@a.txt https://api.stripe.com/v1/files")["method"], "POST")
        self.assertIsNone(asks("curl https://api.stripe.com/v1/refunds"))
        self.assertIsNone(asks("curl -G https://api.stripe.com/v1/refunds -d limit=3"))
        self.assertEqual(self.call("curl -G https://x.example/a -d limit=3")["query"], "limit=3")
        self.assertEqual(self.call("curl -I https://x.example/a -d x=1")["method"], "HEAD")
        self.assertEqual(self.call("curl -T f.txt https://x.example/a")["method"], "PUT")

    def test_bodies(self):
        self.assertEqual(self.call("curl -d a=1 -d b=2 https://x.example")["body"], "a=1&b=2")
        self.assertEqual(self.call("curl --data-urlencode 'q=a b' https://x.example")["body"], "q=a%20b")
        self.assertIn("cloudflare.purge", asks(
            "curl -X POST https://api.cloudflare.com/client/v4/zones/z/purge_cache --data '{\"purge_everything\":true}'"))
        self.assertIsNone(asks(
            "curl -X POST https://api.cloudflare.com/client/v4/zones/z/purge_cache --data '{\"files\":[\"a\"]}'"))

    def test_body_from_a_file(self):
        with tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "q.json").write_text('{"query": "mutation {\\n volumeDelete(volumeId: 1)\\n}"}\n')
            command = "curl https://backboard.railway.com/graphql/v2 -d @q.json"
            self.assertIn("railway.volume", asks(command, cwd))
            Path(cwd, "q.json").write_text('{"query": "query { volumes { id } }"}')
            self.assertIsNone(asks(command, cwd))

    def test_form_fields(self):
        call = self.call("curl -F name=x -F 'operations={\"query\":\"mutation { volumeDelete(id: 1) }\"}' "
                         "https://backboard.railway.com/graphql/v2")
        self.assertEqual(call["graphql"], ["volumeDelete"])
        self.assertEqual(self.call("curl -F a=1 -F b=2 https://x.example")["body"], "a=1&b=2")

    def test_url_flag_and_many_urls(self):
        self.assertIn("vercel.project", asks("curl -X DELETE --url https://api.vercel.com/v9/projects/p"))
        calls = guard.shell_calls("curl -X DELETE https://api.vercel.com/v1/x https://api.vercel.com/v9/projects/p")
        self.assertEqual([c["path"] for c in calls], ["/v1/x", "/v9/projects/p"])
        self.assertIn("vercel.project", asks("curl -X DELETE https://api.vercel.com/v1/x https://api.vercel.com/v9/projects/p"))
        calls = guard.shell_calls("curl -X DELETE https://a.example/1 --next https://a.example/2")
        self.assertEqual([c["method"] for c in calls], ["DELETE", "GET"])

    def test_quoting(self):
        self.assertIn("vercel.project", asks("curl -X 'DELETE' \"https://api.vercel.com/v9/projects/my%20app\""))
        self.assertEqual(self.call("curl \"https://x.example/a b\" -d \"say \\\"hi\\\"\"")["body"], 'say "hi"')
        self.assertEqual(self.call("curl https://x.example/%2Fx")["path"], "//x")

    def test_unknown_host_says_nothing(self):
        for command in ('curl -X DELETE "$API/v9/projects/p"', "curl -X DELETE https://$HOST/v9/projects/p",
                        "curl -X DELETE ${VERCEL}/v9/projects/p", "curl -X DELETE https://`host`/v9/projects/p"):
            self.assertIsNone(asks(command), command)
        self.assertIn("vercel.project", asks('curl -X DELETE "https://api.vercel.com/v9/projects/$P"'))

    def test_chains_pipes_and_wrappers(self):
        for command in ("cd app && curl -X DELETE https://api.heroku.com/apps/a",
                        "true; curl -X DELETE https://api.heroku.com/apps/a | jq .",
                        "curl https://x.example || curl -X DELETE https://api.heroku.com/apps/a &",
                        "sudo -u me env TOKEN=x curl -X DELETE https://api.heroku.com/apps/a",
                        "timeout 30 /usr/bin/curl -X DELETE https://api.heroku.com/apps/a 2>&1 > out.json",
                        "bash -lc 'curl -X DELETE https://api.heroku.com/apps/a'",
                        "echo $(curl -s -X DELETE https://api.heroku.com/apps/a)",
                        "if true; then\n  curl -X DELETE https://api.heroku.com/apps/a\nfi"):
            self.assertIn("heroku.app", asks(command) or "", command)
        self.assertIsNone(asks("echo 'curl -X DELETE https://api.heroku.com/apps/a'"))
        self.assertIsNone(asks("curl https://api.heroku.com/apps/a && echo -X DELETE"))
        self.assertIsNone(asks("# curl -X DELETE https://api.heroku.com/apps/a"))

    def test_stdin(self):
        query = '{"query":"mutation { serviceDelete(id: 1) }"}'
        url = "https://backboard.railway.com/graphql/v2"
        for command in (f"echo '{query}' | curl -d @- {url}", f"printf '{query}' | curl --json @- {url}",
                        f"curl -d @- {url} <<'EOF'\n{query}\nEOF", f"curl -d @- {url} <<< '{query}'"):
            self.assertIn("railway.service", asks(command), command)
        self.assertIsNone(asks(f"echo '{{\"query\":\"query {{ me {{ id }} }}\"}}' | curl -d @- {url}"))


class UnreadGraphql(unittest.TestCase):
    """FORMAT.md: a reader that cannot read the body of a call a graphql rule would otherwise match asks."""

    def test_asks_when_the_query_cannot_be_read(self):
        for command in ("curl -d @- https://backboard.railway.com/graphql/v2",
                        "curl -d @missing.json https://backboard.railway.com/graphql/v2",
                        'curl -d "$PAYLOAD" https://backboard.railway.com/graphql/v2',
                        "curl -d '{\"query\": \"mutation { volumeDelete(\"}' https://backboard.railway.com/graphql/v2",
                        'gh api graphql -f query="$(cat q.graphql)"'):
            why = asks(command)
            self.assertIn("could not read", why or "", command)

    def test_says_nothing_elsewhere(self):
        self.assertIsNone(asks("curl -d @- https://api.example.com/graphql"))
        self.assertIsNone(asks('curl -X POST -d "$PAYLOAD" https://api.stripe.com/v1/customers'))
        self.assertIsNone(asks("curl https://backboard.railway.com/graphql/v2"))


class GraphqlRoots(unittest.TestCase):
    def test_root_fields(self):
        roots = guard.graphql_roots
        self.assertEqual(roots("mutation { volumeDelete(volumeId: \"x\") }"), ["volumeDelete"])
        self.assertEqual(roots("mutation Kill($id: String!) @x { a: volumeDelete(volumeId: $id) b: serviceDelete(id: $id) }"),
                         ["volumeDelete", "serviceDelete"])
        self.assertEqual(roots("{ me { volumeDelete } }"), ["me"])
        self.assertEqual(roots("query A { me { id } } mutation B { projectDelete(id: 1) }"), ["me", "projectDelete"])
        self.assertEqual(roots("mutation { ...F } fragment F on Mutation { volumeDelete(id: 1) }"), ["volumeDelete"])
        self.assertEqual(roots("mutation { ... on Mutation { serviceDelete(id: 1) } }"), ["serviceDelete"])
        self.assertEqual(roots('# volumeDelete\nmutation { note(text: "volumeDelete { }") }'), ["note"])
        self.assertEqual(roots('mutation { note(text: """a } b""") }'), ["note"])
        for broken in ("mutation { volumeDelete(", "mutation", "not graphql", "{ ...Missing }"):
            self.assertIsNone(roots(broken), broken)


class Gh(unittest.TestCase):
    def test_default_host_and_method(self):
        call = guard.shell_calls("gh api repos/acme/app")[0]
        self.assertEqual((call["method"], call["host"], call["path"]), ("GET", "api.github.com", "/repos/acme/app"))
        self.assertEqual(guard.shell_calls("gh api /user -f name=x")[0]["method"], "POST")
        self.assertEqual(guard.shell_calls("gh api repos/a/b/issues -X GET -f state=open")[0]["query"], "state=open")
        self.assertEqual(guard.shell_calls("gh api --hostname ghe.acme.com repos/a/b")[0]["host"], "ghe.acme.com")

    def test_fields(self):
        self.assertIn("github.visibility", asks("gh api --method PATCH repos/acme/app -f visibility=public"))
        self.assertIsNone(asks("gh api --method PATCH repos/acme/app -f description=public"))
        self.assertIn("github.force-ref", asks("gh api -X PATCH repos/{owner}/{repo}/git/refs/heads/main -F force=true"))
        self.assertIsNone(asks("gh api -X PATCH repos/{owner}/{repo}/git/refs/heads/main -F force=false"))
        body = json.loads(guard.shell_calls("gh api -X POST x -F n=3 -f s=3 -f a[]=1 -f a[]=2 -f o[k]=v")[0]["body"])
        self.assertEqual(body, {"n": 3, "s": "3", "a": ["1", "2"], "o": {"k": "v"}})

    def test_delete(self):
        self.assertTrue(asks("gh api -X DELETE repos/acme/app"))
        self.assertIn("github.transfer", asks("gh api repos/acme/app/transfer -f new_owner=evil"))
        self.assertIsNone(asks("gh api repos/acme/app/pulls"))

    def test_graphql(self):
        self.assertIn("github.graphql", asks(
            "gh api graphql -f query='mutation($id: ID!) { deleteRef(input: {refId: $id}) { clientMutationId } }' -f id=R1"))
        self.assertIsNone(asks("gh api graphql -f query='mutation { addStar(input: {starrableId: \"x\"}) { clientMutationId } }'"))
        self.assertIn("github.graphql-force", asks(
            "gh api graphql -f query='mutation { updateRef(input: $i) { clientMutationId } }' -F i[force]=true"))
        self.assertIsNone(asks("gh api graphql -f query='mutation { updateRef(input: $i) { clientMutationId } }' -F i[oid]=a"))
        with tempfile.TemporaryDirectory() as cwd:
            Path(cwd, "q.graphql").write_text("mutation { archiveRepository(input: {}) { clientMutationId } }")
            self.assertIn("github.graphql", asks("gh api graphql -F query=@q.graphql", cwd))


class HttpieAndWget(unittest.TestCase):
    def test_httpie(self):
        self.assertIn("heroku.app", asks("http DELETE api.heroku.com/apps/a"))
        self.assertIsNone(asks("http api.heroku.com/apps/a"))
        self.assertIn("notion.trash", asks("https PATCH api.notion.com/v1/pages/p in_trash:=true Authorization:x"))
        self.assertIsNone(asks("https PATCH api.notion.com/v1/pages/p in_trash:=false"))
        self.assertIn("stripe.refund", asks("http -f api.stripe.com/v1/refunds charge=ch_1"))
        call = guard.shell_calls("http :8001/api/v1/namespaces/x q==1")[0]
        self.assertEqual((call["method"], call["host"], call["query"]), ("GET", "localhost", "q=1"))
        self.assertIsNone(asks("http --offline DELETE api.heroku.com/apps/a"))
        self.assertIn("railway.service", asks(
            "echo '{\"query\":\"mutation { serviceDelete(id: 1) }\"}' | http POST backboard.railway.com/graphql/v2"))

    def test_wget(self):
        self.assertIn("render.delete", asks("wget -q --method=DELETE https://api.render.com/v1/services/s"))
        self.assertIn("render.delete", asks("wget -nv --method DELETE -O - https://api.render.com/v1/services/s"))
        self.assertIsNone(asks("wget https://api.render.com/v1/services/s"))
        self.assertIn("stripe.refund", asks("wget --post-data charge=ch_1 https://api.stripe.com/v1/refunds"))


class Mcp(unittest.TestCase):
    def test_fetch_tool_with_url_and_method(self):
        why = guard.check("mcp__fetch__request", {"url": "https://api.vercel.com/v9/projects/p", "method": "DELETE"})
        self.assertIn("vercel.project", why)
        why = guard.check("mcp__http__fetch", {"url": "https://backboard.railway.com/graphql/v2", "method": "POST",
                                               "body": {"query": "mutation { volumeDelete(id: 1) }"}})
        self.assertIn("railway.volume", why)

    def test_conservative(self):
        for tool, given in (("mcp__fetch__fetch", {"url": "https://api.vercel.com/v9/projects/p"}),
                            ("mcp__fetch__request", {"url": "https://api.vercel.com/v9/projects/p", "method": "GET"}),
                            ("mcp__x__y", {"url": "api.vercel.com/v9/projects/p", "method": "DELETE"}),
                            ("mcp__x__y", {"url": "https://api.vercel.com/v9/projects/p", "method": "remove"}),
                            ("WebFetch", {"url": "https://api.vercel.com/v9/projects/p", "method": "DELETE"})):
            self.assertIsNone(guard.check(tool, given), (tool, given))


class NeverInTheWay(unittest.TestCase):
    def test_parse_errors_say_nothing(self):
        for command in ("curl -X DELETE 'https://api.heroku.com/apps/a", "curl -X", "curl --url", "gh api",
                        "http", "wget --method", "curl $(", "curl `", "((((", "curl -d @/dev/null/x https://x.example",
                        "curl https://[bad/x", "curl -X DELETE https://api.heroku.com:99999/apps/a", "\\"):
            asks(command)  # must not raise
        with mock.patch.object(guard, "shell_calls", side_effect=RecursionError):
            self.assertIsNone(asks("curl -X DELETE https://api.heroku.com/apps/a"))

    def test_never_exits_2(self):
        self.assertEqual(run("--host", "nope").returncode, 1)
        self.assertEqual(run("--host", "cursor", stdin="[]").returncode, 0)


class Feeds(unittest.TestCase):
    def test_v1_feed_without_http_rules(self):
        v1 = {"version": 1, "rules": [{"tool": "*", "action": "approve", "command": r"\bnpm\s+publish\b", "why": "x"}]}
        with mock.patch.object(guard, "feed_rules", return_value=v1):
            self.assertIn("rule 1", asks("npm publish"))
            self.assertIsNone(asks("curl -X DELETE https://api.heroku.com/apps/a"))

    def test_http_rules_the_guard_cannot_use_are_skipped(self):
        good = {"id": "t.ok", "host": "a.example", "method": ["DELETE"], "path": "^/x$", "action": "approve", "why": "w"}
        feed = {"version": 3, "rules": [], "http": [
            "not a rule", {"id": "t.nohost", "method": ["DELETE"], "path": "^/x$"},
            {**good, "id": "t.unknown-field", "header": "x"}, {**good, "id": "t.bad-regex", "path": "("},
            {**good, "id": "t.deny", "action": "deny"}, good]}
        with mock.patch.object(guard, "feed_rules", return_value=feed):
            self.assertIn("t.ok", asks("curl -X DELETE https://a.example/x"))
        with mock.patch.object(guard, "feed_rules", return_value={**feed, "http": "nonsense"}):
            self.assertIsNone(asks("curl -X DELETE https://a.example/x"))


class Hosts(unittest.TestCase):
    def test_claude_code_settings(self):
        hooks = json.loads(run("--settings").stdout)["hooks"]["PreToolUse"]
        self.assertEqual(hooks[0]["matcher"], "*")
        self.assertEqual(json.loads(run("--settings", "--host", "claude").stdout), json.loads(run("--settings").stdout))

    def test_claude_code_http(self):
        call = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/",
                "tool_input": {"command": "curl -X DELETE https://api.vercel.com/v9/projects/p"}}
        out = json.loads(run(stdin=json.dumps(call)).stdout)["hookSpecificOutput"]
        self.assertEqual((out["hookEventName"], out["permissionDecision"]), ("PreToolUse", "ask"))
        self.assertIn("vercel.project", out["permissionDecisionReason"])
        call["tool_input"]["command"] = "curl https://api.vercel.com/v9/projects/p"
        self.assertEqual(run(stdin=json.dumps(call)).stdout, "")

    def test_cursor_settings(self):
        config = json.loads(run("--settings", "--host", "cursor").stdout)
        self.assertEqual(config["version"], 1)
        self.assertEqual(set(config["hooks"]), {"beforeShellExecution", "beforeMCPExecution"})
        for hooks in config["hooks"].values():
            self.assertTrue(hooks[0]["command"].endswith("guard.py --host cursor"))
            self.assertIsInstance(hooks[0]["timeout"], int)

    def test_cursor_shell(self):
        call = {"hook_event_name": "beforeShellExecution", "conversation_id": "c", "generation_id": "g",
                "command": "curl -X DELETE https://api.vercel.com/v9/projects/p", "cwd": "/tmp", "sandbox": False,
                "workspace_roots": ["/tmp"]}
        out = json.loads(run("--host", "cursor", stdin=json.dumps(call)).stdout)
        self.assertEqual(set(out), {"permission", "user_message", "agent_message"})
        self.assertEqual(out["permission"], "ask")
        self.assertIn("vercel.project", out["user_message"])
        self.assertIn("git history", json.loads(run("--host", "cursor", stdin=json.dumps(
            {**call, "command": "git reset --hard"})).stdout)["user_message"])
        self.assertEqual(run("--host", "cursor", stdin=json.dumps({**call, "command": "ls"})).stdout, "")

    def test_cursor_mcp(self):
        call = {"hook_event_name": "beforeMCPExecution", "tool_name": "request", "mcp_server_name": "fetch",
                "tool_input": json.dumps({"url": "https://api.vercel.com/v9/projects/p", "method": "DELETE"}),
                "command": "npx some-fetch-server", "workspace_roots": ["/tmp"]}
        out = json.loads(run("--host", "cursor", stdin=json.dumps(call)).stdout)
        self.assertEqual(out["permission"], "ask")
        self.assertIn("vercel.project", out["agent_message"])
        quiet = {**call, "tool_input": json.dumps({"url": "https://api.vercel.com/v9/projects/p", "method": "GET"})}
        self.assertEqual(run("--host", "cursor", stdin=json.dumps(quiet)).stdout, "")
        self.assertEqual(run("--host", "cursor", stdin=json.dumps({**call, "tool_input": "not json"})).stdout, "")


class PublishedKey(unittest.TestCase):
    def test_built_in_key_verifies_the_signed_feed(self):
        source = (HERE / "guard.py").read_text()
        key = source.split('os.environ.get("QUARTER_FEED_KEY", "', 1)[1].split('"', 1)[0]
        self.assertEqual(key, (HERE / "verify-key.txt").read_text().strip())
        signed = json.loads((HERE / "feed.json").read_text())
        self.assertEqual(guard.verified(signed, key), BODY)


if __name__ == "__main__":
    unittest.main()
