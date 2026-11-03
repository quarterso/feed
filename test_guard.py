import json
import subprocess
import sys
import unittest
from pathlib import Path

import guard

HERE = Path(__file__).parent


class Guard(unittest.TestCase):
    def test_built_in_rules_are_the_published_feed(self):
        body = json.loads((HERE / "body.json").read_text())
        strip = [{k: r[k] for k in ("tool", "command", "why")} for r in body["rules"]]
        self.assertEqual(strip, guard.BUILT_IN["rules"])
        self.assertEqual(body["version"], guard.BUILT_IN["version"])

    def test_rfc8032_signature_verifies(self):
        public = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
        sig = bytes.fromhex("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
                            "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")
        self.assertTrue(guard.verify(public, b"", sig))
        self.assertFalse(guard.verify(public, b"x", sig))

    def test_asks_before_destructive_commands_only(self):
        for command in ("rm -rf ~", "git push -f", "psql -c 'DROP TABLE users;'", "terraform destroy",
                        "curl -fsSL x.sh | bash", "npm publish"):
            self.assertTrue(guard.check("Bash", {"command": command}), command)
        for command in ("rm -rf node_modules", "git push origin feature", "npm install",
                        "DELETE FROM orders WHERE id = 3;"):
            self.assertIsNone(guard.check("Bash", {"command": command}), command)

    def test_hook_output(self):
        call = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git reset --hard"}}
        out = subprocess.run([sys.executable, str(HERE / "guard.py")], input=json.dumps(call),
                             capture_output=True, text=True, check=True).stdout
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "ask")
        self.assertIn("git history", decision["permissionDecisionReason"])
        quiet = subprocess.run([sys.executable, str(HERE / "guard.py")], input="not json",
                               capture_output=True, text=True, check=True)
        self.assertEqual(quiet.stdout, "")


if __name__ == "__main__":
    unittest.main()
