"""Every rule in body.json against its two cases in cases.json: a call it must match, and a
near miss it must not. HTTP rules are checked with the reference reading of FORMAT.md,
guard.http_matches, which guard.py also uses on the calls it reads."""

import json
import re
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

import guard
from guard import HTTP_FIELDS, MCP_SERVER_FIELDS, MCP_TOOL_FIELDS, globs, http_matches

HERE = Path(__file__).parent
BODY = json.loads((HERE / "body.json").read_text())
CASES = json.loads((HERE / "cases.json").read_text())


class Rulebook(unittest.TestCase):
    def test_every_rule_has_an_id_a_source_and_two_cases(self):
        about = {a["rule"]: a for a in BODY["about"]}
        self.assertEqual(sorted(about), list(range(1, len(BODY["rules"]) + 1)))
        ids = [a["id"] for a in BODY["about"]] + [h["id"] for h in BODY["http"]]
        self.assertEqual(len(ids), len(set(ids)), "ids are unique")
        self.assertEqual(set(ids) | set(ask_ids()), set(CASES))
        for rule in BODY["http"]:
            self.assertLessEqual(set(rule), HTTP_FIELDS, rule["id"])
            self.assertEqual(rule["action"], "approve", rule["id"])
            self.assertTrue(rule["why"] and rule["source"].startswith("https://"), rule["id"])
            for field in ("path", "body", "query"):
                if field in rule:
                    re.compile(rule[field])
        for a in BODY["about"][7:]:
            self.assertTrue(a["source"].startswith("https://"), a["id"])

    def test_v1_rules_are_unchanged(self):
        """Rules 1 to 7 keep their numbers and patterns, so a version 1 record still reads."""
        self.assertEqual([a["id"] for a in BODY["about"][:7]],
                         ["shell.rm-root", "shell.disk", "sql.drop", "git.history", "cloud.teardown", "publish",
                          "shell.pipe"])
        for rule in BODY["rules"]:
            self.assertEqual(set(rule), {"tool", "action", "command", "why"})

    def test_each_command_rule_catches_its_case_and_nothing_catches_the_near_miss(self):
        for n, (rule, about) in enumerate(zip(BODY["rules"], BODY["about"], strict=True), 1):
            case = CASES[about["id"]]
            with self.subTest(about["id"]):
                self.assertTrue(re.search(rule["command"], case["match"], re.IGNORECASE), case["match"])
                self.assertIsNone(guard.check("Bash", {"command": case["miss"]}), case["miss"])

    def test_each_http_rule_catches_its_case_and_misses_the_near_miss(self):
        for rule in BODY["http"]:
            case = CASES[rule["id"]]
            with self.subTest(rule["id"]):
                self.assertTrue(http_matches(rule, case["match"]), case["match"])
                self.assertFalse(http_matches(rule, case["miss"]), case["miss"])

    def test_no_http_rule_fires_on_every_read(self):
        """A rule that fires on every GET is worse than none. GET is held only where a body or
        query pattern narrows it (AWS query actions), and only Slack, whose methods take any
        verb, matches every method."""
        for rule in BODY["http"]:
            methods = globs(rule["method"])
            if "GET" in methods:
                self.assertTrue("body" in rule or "query" in rule, rule["id"])
            if "*" in methods:
                self.assertEqual(rule["service"], "Slack", rule["id"])

    def test_the_pocketos_call_is_held(self):
        """April 2026: one Railway GraphQL call deleted a production volume and its backups."""
        call = {"method": "POST", "host": "backboard.railway.com", "path": "/graphql/v2",
                "graphql": ["volumeDelete"]}
        held = [r["id"] for r in BODY["http"] if http_matches(r, call)]
        self.assertEqual(held, ["railway.volume"])


def ask_ids():
    return [f"mcp.{s['server']}.{t['tool']}" for s in BODY["mcp"] for t in s["tools"] if t["rating"] == "ask"]


class McpRatings(unittest.TestCase):
    def test_every_rating_has_a_source_and_every_ask_two_cases(self):
        self.assertEqual(BODY["version"], 4)
        servers = [s["server"] for s in BODY["mcp"]]
        self.assertEqual(len(servers), len(set(servers)), "server ids are unique")
        for s in BODY["mcp"]:
            self.assertEqual(set(s), MCP_SERVER_FIELDS, s["server"])
            self.assertTrue(s["names"] and s["package"] and s["source"].startswith("https://"), s["server"])
            tools = [t["tool"] for t in s["tools"]]
            self.assertEqual(len(tools), len(set(tools)), s["server"])
            for t in s["tools"]:
                with self.subTest(f"{s['server']}.{t['tool']}"):
                    self.assertLessEqual(set(t), MCP_TOOL_FIELDS)
                    self.assertIn(t["rating"], ("ask", "watch"))
                    self.assertTrue(t["why"] and "\u2014" not in t["why"])
                    self.assertTrue(t.get("source", s["source"]).startswith("https://"))
                    if "input" in t:
                        re.compile(t["input"])
        self.assertEqual(len(ask_ids()), len(set(ask_ids())))

    def test_each_ask_rating_asks_on_its_case_and_stays_silent_on_the_near_miss(self):
        """The near miss is a call to the same server that must not ask: another tool, or the same
        tool with an input the rating does not cover."""
        why = {f"mcp.{s['server']}.{t['tool']}": t["why"] for s in BODY["mcp"] for t in s["tools"]}
        with mock.patch.object(guard, "feed_rules", return_value=BODY):
            for rid in ask_ids():
                case = CASES[rid]
                with self.subTest(rid):
                    self.assertEqual(guard.check(case["match"]["tool"], case["match"]["input"]),
                                     f"Quarter rating: {why[rid]}")
                    self.assertIsNone(guard.check(case["miss"]["tool"], case["miss"]["input"]), case["miss"])

    def test_watch_ratings_never_ask(self):
        with mock.patch.object(guard, "feed_rules", return_value=BODY):
            for s in BODY["mcp"]:
                for t in s["tools"]:
                    if t["rating"] == "watch":
                        self.assertIsNone(guard.check(f"mcp__{s['names'][0].strip('*')}__{t['tool']}", {}), t["tool"])


PAYEE_FIELDS = {"id", "service", "pay_to", "hosts", "status", "prices", "why", "source"}


class Payees(unittest.TestCase):
    def test_every_payee_is_matched_somehow_and_has_a_source(self):
        ids = [p["id"] for p in BODY["payees"]]
        self.assertEqual(len(ids), len(set(ids)), "payee ids are unique")
        for p in BODY["payees"]:
            with self.subTest(p["id"]):
                self.assertLessEqual(set(p), PAYEE_FIELDS)
                self.assertIn(p["status"], ("known", "caution"))
                self.assertTrue(p.get("pay_to") or p.get("hosts"))
                self.assertTrue(p["service"] and p["why"] and "\u2014" not in p["why"])
                self.assertTrue(p["source"].startswith("https://"))
                for to in p.get("pay_to", []):
                    self.assertEqual(set(to), {"address", "network"})
                    self.assertRegex(to["network"], r"^[a-z0-9-]+:[A-Za-z0-9]+$")
                for price in p.get("prices", []):
                    self.assertEqual(set(price), {"resource", "max_usd"})
                    self.assertTrue(price["resource"].startswith("https://") and "?" not in price["resource"])
                    self.assertGreater(Decimal(price["max_usd"]), 0)


if __name__ == "__main__":
    unittest.main()
