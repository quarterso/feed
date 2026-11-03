#!/usr/bin/env python3
"""Quarter guard: asks you before a coding agent runs a destructive command.

A Claude Code PreToolUse hook. It checks each tool call against the Quarter feed's rules
and, on a match, makes Claude Code ask you first. It never refuses anything on its own.
The rules are built in, so it works offline; a newer signed feed replaces them once a day.
Standard library only. Print the settings to add with: python3 guard.py --settings
"""

import fnmatch
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

FEED = os.environ.get("QUARTER_FEED", "https://quarterso.github.io/feed/feed.json")
FEED_KEY = os.environ.get("QUARTER_FEED_KEY", "")  # ed25519-pub:..., once the feed is signed
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "quarter-guard" / "feed.json"
DAY = 86_400

BUILT_IN = {"version": 1, "rules": [
    {"tool": "*", "why": "deletes a root, home or working directory",
     "command": r"\brm\s+-\w*(rf|fr)\w*\s+(/\*?|~/?|\$HOME/?|\*|\.\.?/?)(\s|;|&|$)"},
    {"tool": "*", "why": "formats or overwrites a disk",
     "command": r"\bmkfs(\.\w+)?\s|\bdd\s[^;&|]*\bof=/dev/"},
    {"tool": "*", "why": "drops or empties a database table, or deletes every row",
     "command": r"\b(drop\s+(database|schema|table)|truncate\s+table)\s|\bdelete\s+from\s+[\w.]+\s*(;|$)"},
    {"tool": "*", "why": "rewrites or deletes git history, or throws away uncommitted work",
     "command": r"\bgit\s+push\b[^;&|]*(--force\b|\s-f\b|--mirror\b|--delete\b)|\bgit\s+reset\s+--hard\b"
                r"|\bgit\s+clean\s+-\w*f"},
    {"tool": "*", "why": "tears down cloud resources",
     "command": r"\b(terraform|pulumi|cdk)\s+destroy\b|\bkubectl\s+delete\b|\bhelm\s+(uninstall|delete)\b"
                r"|\baws\s+\S+\s+(delete|terminate)-|\baws\s+s3\s+(rm|rb)\b|\b(gcloud|az)\s[^;&|]*\sdelete\b"},
    {"tool": "*", "why": "publishes a package, image or release, or deletes a repository",
     "command": r"\b(npm|pnpm|yarn)\s+publish\b|\btwine\s+upload\b|\bcargo\s+publish\b|\bdocker\s+push\b"
                r"|\bgh\s+(release\s+create|repo\s+delete)\b"},
    {"tool": "*", "why": "runs a downloaded script straight in a shell",
     "command": r"\b(curl|wget)\s[^|;&]*\|\s*(sudo\s+)?(ba|z)?sh\b"},
]}


# Ed25519 verification (RFC 8032), the reference algorithm.
_p = 2**255 - 19
_q = 2**252 + 27742317777372353535851937790883648493
_d = -121665 * pow(121666, _p - 2, _p) % _p
_I = pow(2, (_p - 1) // 4, _p)


def _add(P, Q):
    x1, y1, z1, t1 = P
    x2, y2, z2, t2 = Q
    a, b = (y1 - x1) * (y2 - x2) % _p, (y1 + x1) * (y2 + x2) % _p
    c, d = 2 * t1 * t2 * _d % _p, 2 * z1 * z2 % _p
    e, f, g, h = b - a, d - c, d + c, b + a
    return (e * f % _p, g * h % _p, f * g % _p, e * h % _p)


def _mul(s, P):
    Q = (0, 1, 1, 0)
    while s:
        if s & 1:
            Q = _add(Q, P)
        P, s = _add(P, P), s >> 1
    return Q


def _x(y, sign):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p) % _p
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p:
        x = x * _I % _p
    if (x * x - x2) % _p:
        return None
    return _p - x if x & 1 != sign else x


def _point(data):
    y = int.from_bytes(data, "little")
    x = _x(y & ((1 << 255) - 1), y >> 255)
    return None if x is None else (x, y & ((1 << 255) - 1), 1, x * (y & ((1 << 255) - 1)) % _p)


_gy = 4 * pow(5, _p - 2, _p) % _p
_G = (_x(_gy, 0), _gy, 1, _x(_gy, 0) * _gy % _p)


def verify(public: bytes, msg: bytes, sig: bytes) -> bool:
    if len(public) != 32 or len(sig) != 64:
        return False
    A, R, s = _point(public), _point(sig[:32]), int.from_bytes(sig[32:], "little")
    if A is None or R is None or s >= _q:
        return False
    k = int.from_bytes(hashlib.sha512(sig[:32] + public + msg).digest(), "little") % _q
    P, Q = _mul(s, _G), _add(R, _mul(k, A))
    return (P[0] * Q[2] - Q[0] * P[2]) % _p == 0 and (P[1] * Q[2] - Q[1] * P[2]) % _p == 0


def verified(envelope, key: str):
    """The feed body if it is signed with key, else None."""
    try:
        body = envelope["feed"]
        msg = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        public, sig = bytes.fromhex(key.removeprefix("ed25519-pub:")), bytes.fromhex(envelope["signature"])
        return body if isinstance(body, dict) and verify(public, msg, sig) else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def feed_rules() -> dict:
    """The newest rules we can trust: a verified feed if newer than the built-in ones."""
    if not FEED_KEY:
        return BUILT_IN
    try:
        fresh = CACHE.exists() and time.time() - CACHE.stat().st_mtime < DAY
        if not fresh:
            with urllib.request.urlopen(FEED, timeout=3) as resp:
                raw = resp.read(1_000_000)
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_bytes(raw)
        body = verified(json.loads(CACHE.read_bytes()), FEED_KEY)
    except (OSError, ValueError):
        body = None
    newer = body and isinstance(body.get("version"), int) and body["version"] > BUILT_IN["version"]
    return body if newer and isinstance(body.get("rules"), list) else BUILT_IN


def text(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        value = list(value.values())
    return " ".join(text(v) for v in value) if isinstance(value, list) else ""


def check(tool: str, tool_input) -> str | None:
    """Why a rule asks about this call, or None."""
    said = text(tool_input)
    for n, rule in enumerate(feed_rules()["rules"], 1):
        if rule.get("action", "approve") != "approve" or not isinstance(rule.get("tool"), str):
            continue  # the guard only ever asks
        try:
            if fnmatch.fnmatchcase(tool.lower(), rule["tool"].lower()) and (
                    not rule.get("command") or re.search(rule["command"], said, re.IGNORECASE)):
                return f"Quarter feed rule {n}: {rule.get('why') or 'matches ' + rule.get('command', '')}"
        except re.error:
            continue
    return None


SETTINGS = {"hooks": {"PreToolUse": [{"matcher": "*", "hooks": [
    {"type": "command", "command": "python3", "args": [str(Path(__file__).resolve())], "timeout": 10}]}]}}


def main() -> None:
    if sys.argv[1:] == ["--settings"]:
        print(json.dumps(SETTINGS, indent=2))
        return
    try:
        call = json.load(sys.stdin)
        why = check(str(call.get("tool_name", "")), call.get("tool_input"))
    except (ValueError, AttributeError):
        return  # not a hook call we understand: the normal permission flow applies
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "ask", "permissionDecisionReason": why}}))


if __name__ == "__main__":
    main()
