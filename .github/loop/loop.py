#!/usr/bin/env python3
"""Klocki pętli bez agenta: sonda poświadczenia, raport sesji, przyczyna maszynowa.

Zero agenta. Uruchamiany z checkoutu gałęzi domyślnej, nigdy z gałęzi zadania —
agent nie może zmienić kodu, który go pilnuje.

Podpolecenia: probe, export, publish.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "")
MARK = "<!-- session-report -->"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
BOT = "github-actions[bot]"
# Pola raportu pisane przez epilog; publikacja raportu agenta ich nie kasuje.
OWNED = ("wznow_po", "przyczyna")


# ---------------------------------------------------------------- gh

def gh(*args, inp=None, check=True):
    r = subprocess.run(["gh", *args], input=inp, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit("gh %s: %s" % (" ".join(args[:3]), r.stderr.strip()))
    return r.stdout


def api(path, *fields, method="GET", inp=None):
    args = ["api", path, "-X", method]
    for f in fields:
        args += ["-F", f]
    out = gh(*args, inp=inp)
    return json.loads(out) if out.strip() else None


def api_list(path):
    out = gh("api", path, "--paginate", "--jq", ".[]")
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def now():
    return datetime.now(timezone.utc)


def parse_time(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def issue(n):
    return api("repos/%s/issues/%s" % (REPO, n))


def probe():
    """Sonda poświadczenia: 200 żyje, 401 martwy, 403 odwołany. Nie zjada limitu."""
    req = urllib.request.Request("https://api.anthropic.com/v1/models", headers={
        "Authorization": "Bearer " + os.environ.get("CLAUDE_CODE_OAUTH_TOKEN", ""),
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "oauth-2025-04-20",
    })
    try:
        return urllib.request.urlopen(req, timeout=20).status
    except urllib.error.HTTPError as e:
        return e.code
    except OSError:
        return 0    # przejściowa awaria sieci to nie martwe poświadczenie


# ---------------------------------------------------------------- raport

def trusted(c):
    return c["author_association"] in TRUSTED or c["user"]["login"] == BOT


def trusted_comments(n):
    return [c for c in api_list("repos/%s/issues/%s/comments" % (REPO, n)) if trusted(c)]


def find_report(n):
    found = None
    for c in trusted_comments(n):
        if c["body"].startswith(MARK):
            found = c
    return found


YAML_BLOCK = re.compile(r"```yaml\n(.*?)```", re.S)


def fields(body):
    m = YAML_BLOCK.search(body)
    d = {}
    for line in (m.group(1).splitlines() if m else []):
        k, sep, v = line.partition(":")
        if sep and k.strip():
            d[k.strip()] = re.split(r"\s+#", v.strip())[0]
    return d


def set_fields(body, upd):
    if not body.startswith(MARK):
        body = MARK + "\n" + body
    if not YAML_BLOCK.search(body):
        body = body.replace(MARK, MARK + "\n```yaml\n```", 1)
    m = YAML_BLOCK.search(body)
    lines = m.group(1).splitlines()
    for k, v in upd.items():
        lines = [l for l in lines if l.split(":", 1)[0].strip() != k]
        if v is not None:
            lines.append("%s: %s" % (k, v))
    return body[:m.start(1)] + "".join(l + "\n" for l in lines) + body[m.end(1):]


def write_report(n, body):
    cur = find_report(n)
    if cur:
        if cur["body"] != body:
            api("repos/%s/issues/comments/%s" % (REPO, cur["id"]), "body=@-", method="PATCH", inp=body)
    else:
        api("repos/%s/issues/%s/comments" % (REPO, n), "body=@-", method="POST", inp=body)


def publish(n, path):
    """Raport agenta z pliku -> jedyny komentarz z markerem; pola epilogu przeżywają."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if not text.startswith(MARK):
        text = MARK + "\n" + text
    cur = find_report(n)
    if cur:
        keep = {k: v for k, v in fields(cur["body"]).items() if k in OWNED and k not in fields(text)}
        text = set_fields(text, keep)
    write_report(n, text)


def export(n, path):
    """Wejście agenta: treść issue + komentarze zaufanych autorów. Agent nie sięga po `gh`."""
    i = issue(n)
    parts = ["# Issue #%s: %s\n\n%s\n" % (n, i["title"], i["body"] or "")]
    for c in trusted_comments(n):
        parts.append("\n---\nkomentarz %s (%s)\n\n%s\n" % (c["id"], c["user"]["login"], c["body"]))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))


def machine_cause(exec_path, exit_code):
    """Przyczyna dosłownie z pliku wykonania, bez interpretacji. Nigdy po `subtype`."""
    if not os.path.exists(exec_path):
        return "brak-pliku-wykonania exit=%s" % exit_code, False, None
    with open(exec_path, encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
    try:
        d = json.loads(raw)
        d = d[-1] if isinstance(d, list) and d else d
    except ValueError:
        d = {}
    parts = []
    if d.get("api_error_status"):
        parts.append("api_error_status=%s" % d["api_error_status"])
    if d.get("terminal_reason"):
        parts.append("terminal_reason=%s" % d["terminal_reason"])
    if d.get("is_error") and not parts:
        parts.append("is_error=true")
    if exit_code not in ("0", "", None):
        parts.append("exit=%s" % exit_code)
    limited = bool(re.search(r"hit your .{0,40}limit|rate_limit", raw, re.I))
    m = re.search(r'"resets?_?[aA]t"\s*:\s*(\d{10,13})', raw)
    reset = None
    if m:
        ts = int(m.group(1))
        reset = datetime.fromtimestamp(ts / 1000 if ts > 10**11 else ts, timezone.utc)
    return " ".join(parts), limited, reset or text_reset(raw)


RESET_TEXT = re.compile(r"resets\s+(?:([A-Z][a-z]{2})\s+(\d{1,2}),?\s+(?:at\s+)?)?(\d{1,2})(?::(\d{2}))?\s*([ap]m)\s*(?:\(([^)]+)\))?", re.I)


def text_reset(raw, ref=None):
    """'resets 7:20am (UTC)' / 'resets Oct 2, 5am (Europe/Warsaw)': termin z tekstu CLI, gdy brak `resetsAt`."""
    m = RESET_TEXT.search(raw)
    if not m:
        return None
    mon, day, h, mi, ap, tz = m.groups()
    try:
        from zoneinfo import ZoneInfo
        zone = ZoneInfo(tz) if tz else timezone.utc
    except Exception:
        zone = timezone.utc
    ref = (ref or now()).astimezone(zone)
    h = int(h) % 12 + (12 if ap.lower() == "pm" else 0)
    t = ref.replace(hour=h, minute=int(mi or 0), second=0, microsecond=0)
    if mon:
        t = t.replace(month=datetime.strptime(mon[:3].title(), "%b").month, day=int(day))
        if t < ref - timedelta(days=1):
            t = t.replace(year=t.year + 1)
    elif t <= ref:
        t += timedelta(days=1)
    return t.astimezone(timezone.utc)


# ---------------------------------------------------------------- main

def main(argv):
    cmd, args = argv[1], argv[2:]
    if cmd == "probe":
        code = probe()
        print("sonda: HTTP %s" % code)
        return 1 if code in (401, 403) else 0
    if cmd == "export":
        export(int(args[0]), args[1])
        return 0
    if cmd == "publish":
        publish(int(args[0]), args[1])
        return 0
    raise SystemExit("nieznane polecenie: " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
