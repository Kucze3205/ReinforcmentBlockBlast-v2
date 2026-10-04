#!/usr/bin/env python3
"""Sztywny kod pętli: dozór, dispatch, epilog, odblokowanie, dozorca.

Zero agenta. Uruchamiany zawsze z checkoutu gałęzi domyślnej, nigdy z gałęzi
zadania — agent nie może zmienić kodu, który go pilnuje. Leży w `.github/`, więc
pętla nie może go edytować (zakaz 2 kontraktu pętli).

Podpolecenia: guard, probe, route, export, publish, finalize, bench, watch, resume.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ.get("GITHUB_REPOSITORY", "")
MARK = "<!-- session-report -->"
TRUSTED = {"OWNER", "MEMBER", "COLLABORATOR"}
BOT = "github-actions[bot]"
# Pola raportu pisane wyłącznie przez epilog i dozorcę; publikacja raportu agenta ich nie kasuje.
OWNED = ("proby", "wznow_po", "kopniecia", "kopniete", "konflikty", "przyczyna", "weryfikacja")
AGENT_STATUSES = {"done", "partial", "blocked", "rejected"}
SECRETS = ("GH_TOKEN", "GITHUB_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN", "ASSETS_READ_TOKEN")
BACKOFF_H = (1, 5, 24)                      # gdy w wyniku sesji nie ma terminu resetu limitu
MAX_ATTEMPTS = 3        # próby wznowienia
MAX_AGE_DAYS = 30       # zapadka wieku
MAX_KICKS = 3           # bezskuteczne kopnięcia
CRASH_STREAK = 3        # kolejne `crashed` bez commita
MAX_SLEEP_S = 340 * 60  # resume.yml: job ma limit 360 min; dłuższy park zostaje dozorcy
GRACE_MIN = 30          # karencja pokrywa opóźnienie dispatchu, nigdy czas pracy
MAX_GEN = 3             # limit pokoleń następców
MAX_CONFLICTS = 3
PROTECTED_PREFIXES = (".github/", ".claude/skills/orchestrator/")
RECORD = "bench/record.json"
NOTES = "docs/journal/"  # zapis cyklu scala się zawsze, także gdy sesja nie jest done
ITER = "loop:iteration "                    # numer cyklu orchestratora, który założył issue; dziedziczy go następca


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


def label_names(i):
    return {l["name"] for l in i["labels"]}


def edit_labels(n, add=(), remove=()):
    args = ["issue", "edit", str(n)]
    for a in add:
        args += ["--add-label", a]
    for r in remove:
        args += ["--remove-label", r]
    if len(args) > 3:
        gh(*args, check=False)


def in_loop(names):
    """Issue należy do pętli <=> ma `loop:iteration N` (pole widzenia) i rolę (kogo uruchomić). Sama `rola:*` nie wystarcza."""
    return any(l.startswith(ITER) for l in names) and any(l.startswith("rola:") for l in names)


def ensure_label(name):
    gh("label", "create", name, "--color", "C5DEF5", "--description", "Cykl pętli, w którym powstało issue", "--force", check=False)


def last_iteration():
    out = gh("label", "list", "--search", "loop:iteration", "--limit", "200", "--json", "name", check=False)
    return max([int(l["name"][len(ITER):]) for l in json.loads(out or "[]")
                if l["name"].startswith(ITER) and l["name"][len(ITER):].isdigit()] or [0])


def blockers(n):
    return api_list("repos/%s/issues/%s/dependencies/blocked_by" % (REPO, n))


def is_unblocked(n):
    return all(b["state"] == "closed" for b in blockers(n))


# ---------------------------------------------------------------- dozór

def autopilot_on():
    """Żywy odczyt zmiennej; gdy API go nie da, wartość z kontekstu przebiegu. Fail-safe: tylko dosłowne `on`."""
    r = subprocess.run(["gh", "api", "repos/%s/actions/variables/AUTOPILOT" % REPO, "--jq", ".value"],
                       capture_output=True, text=True)
    live = r.stdout.strip() if r.returncode == 0 else ""   # GITHUB_TOKEN nie czyta zmiennych: gh drukuje wtedy JSON błędu na stdout
    return (live or os.environ.get("VARS_AUTOPILOT", "")) == "on"


def goal_reached():
    return os.path.exists("GOAL_REACHED")   # cwd = checkout gałęzi domyślnej


def say(msg):
    """Zdanie do logu i do podsumowania przebiegu: przebieg nie kończy się bez powodu na widoku."""
    print(msg)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(msg + "\n\n")


def run_issue(title):
    """'session #12 · implementer' -> 'session #12' (nie myl #12 z #123)."""
    return title.split(" · ")[0]


def guard_ok():
    if not autopilot_on():
        say("AUTOPILOT != on: stój")
        return False
    if goal_reached():
        say("GOAL_REACHED: stój")
        return False
    return True


def set_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    lines = "".join("%s=%s\n" % (k, v) for k, v in kv.items())
    if path:
        with open(path, "a") as fh:
            fh.write(lines)
    else:
        print(lines, end="")


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


def update_report(n, upd, append=""):
    cur = find_report(n)
    body = set_fields(cur["body"] if cur else MARK + "\n", upd)
    if append:
        body = body.rstrip("\n") + "\n\n" + append + "\n"
    write_report(n, body)
    return body


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


def section(body, name):
    m = re.search(r"^## %s\s*\n(.*?)(?=^## |\Z)" % re.escape(name), body or "", re.S | re.M)
    return m.group(1).strip() if m else ""


# ---------------------------------------------------------------- start sesji



# ---------------------------------------------------------------- dispatch

LAUNCHED = set()     # dispatch z tego procesu: `gh run list` pokazuje nowy przebieg z opóźnieniem


def session_runs():
    """Przebiegi sesji bez własnego: epilog pyta o resztę pętli, a jego przebieg jeszcze trwa."""
    out = gh("run", "list", "--workflow", "session.yml", "--limit", "100",
             "--json", "databaseId,displayTitle,status,createdAt")
    own = os.environ.get("GITHUB_RUN_ID", "")
    return [r for r in json.loads(out or "[]") if str(r["databaseId"]) != own]


def launch(n):
    """Jedyny sposób na start sesji: walidacja, deduplikacja, dispatch. Bez zamka: obcych odsiewa trusted()."""
    if not guard_ok():
        return False
    i = issue(n)
    if i["state"] != "open" or not in_loop(label_names(i)):
        return False
    if not is_unblocked(n):
        return False
    if any(run_issue(r["displayTitle"]) == "session #%s" % n and r["status"] in ("queued", "in_progress", "waiting")
           for r in session_runs()):
        return False
    roles = [l[5:] for l in label_names(i) if l.startswith("rola:")]
    gh("workflow", "run", "session.yml", "-f", "issue=%s" % n, "-f", "role=%s" % (roles[0] if len(roles) == 1 else ""))
    LAUNCHED.add(n)
    say("launch #%s" % n)
    return True


def unblock(closed):
    for d in api_list("repos/%s/issues/%s/dependencies/blocking" % (REPO, closed)):
        if d["state"] == "open":
            launch(d["number"])


def halt_dependents(closed, status):
    """Producent nie dowiózł: konsument nie rusza na pusto, tylko zamyka się jako `blocked` (kaskadą
    dalej). Orchestrator rusza normalnie: to on decyduje, co z niedowiezionym cyklem."""
    for d in api_list("repos/%s/issues/%s/dependencies/blocking" % (REPO, closed)):
        if d["state"] != "open":
            continue
        if "rola:orchestrator" in label_names(d):
            launch(d["number"])
        else:
            close_out(d["number"], d, "blocked", {"przyczyna": "producent-#%s-%s" % (closed, status)},
                      "Producent #%s zamknięty jako `%s`: nie dowiózł, więc to zadanie nie ruszyło." % (closed, status))


# ---------------------------------------------------------------- epilog

def clean_env():
    return {k: v for k, v in os.environ.items() if k not in SECRETS}


def git(work, *args, check=True):
    r = subprocess.run(["git", *args], cwd=work, capture_output=True, text=True)
    if check and r.returncode:
        raise SystemExit("git %s: %s" % (" ".join(args), r.stderr.strip()))
    return r


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


def run_verification(work, body):
    """`## Weryfikacja`: polecenia z bloków kodu albo z linii w backtickach. Bez sekretów."""
    text = section(body, "Weryfikacja")
    cmds = re.findall(r"```[a-z]*\n(.*?)```", text, re.S)
    cmds = [c.strip() for c in cmds] or re.findall(r"`([^`\n]+)`", text)
    for c in cmds:
        r = subprocess.run(["bash", "-c", c], cwd=work, env=clean_env(), capture_output=True, text=True, timeout=3600)
        print("$ %s\n%s%s" % (c, r.stdout, r.stderr))     # liczby z udanych poleceń zostają w logu joba
        if r.returncode:
            return False, c + "\n" + (r.stdout + r.stderr)[-1500:]
    return True, ""


def bench(n, work):
    """`rola:bench`: job liczący bez sesji Claude'a. Polecenia bierze z `## Weryfikacja`."""
    base = git(work, "rev-parse", "HEAD").stdout.strip()
    ok, out = run_verification(work, issue(n)["body"])
    commit_bench(n, work)   # przed oceną: wynik przeżywa polecenie, które padło po pomiarze
    # „policzono" = bench/*.json zmienione w tym jobie, w katalogu albo w commitach poleceń
    if ok and not git(work, "diff", "--name-only", base, "HEAD", "--", "bench/*.json").stdout.strip():
        ok, out = False, "Polecenia z `## Weryfikacja` przeszły, ale żaden bench/*.json nie przybył ani się nie zmienił: nic nie policzono."
    print(out)
    with open(os.path.join(os.environ.get("RUNNER_TEMP", "/tmp"), "agent-exit"), "w") as fh:
        fh.write("0" if ok else "1")


def commit_bench(n, work):
    git(work, "add", "-A", "bench")
    git(work, "commit", "-q", "-m", "bench: wynik zadania #%s" % n, check=False)


def merge_main(n, role, work):
    """Rebase na gałąź domyślną, testy, push. Git sam szereguje konkurentów: odrzucony push = ponów."""
    d = os.environ.get("DEFAULT_BRANCH", "main")
    for _ in range(5):
        git(work, "fetch", "origin", d)
        changed = git(work, "diff", "--name-only", "origin/%s...HEAD" % d).stdout.split()
        bad = [f for f in changed if f.startswith(PROTECTED_PREFIXES) or (f == RECORD and role != "bench")]
        if bad:
            return "protected", ", ".join(bad)
        if git(work, "rebase", "origin/%s" % d, check=False).returncode:
            git(work, "rebase", "--abort", check=False)
            return "conflict", ""
        t = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=work,
                           env=clean_env(), capture_output=True, text=True)
        if t.returncode:
            return "tests", (t.stdout + t.stderr)[-1500:]
        if git(work, "push", "origin", "HEAD:refs/heads/%s" % d, check=False).returncode == 0:
            return "merged", ""
    return "conflict", ""


def notes_only(changed):
    return [f for f in changed if f.startswith(NOTES)]


def merge_notes(work):
    """Sesja niedokończona nie scala kodu, ale jej dziennik nie może zostać na task/N."""
    d = os.environ.get("DEFAULT_BRANCH", "main")
    head = git(work, "rev-parse", "HEAD").stdout.strip()
    for _ in range(5):
        git(work, "fetch", "origin", d)
        files = notes_only(git(work, "diff", "--name-only", "--diff-filter=AM", "origin/%s...%s" % (d, head)).stdout.split())
        if not files:
            return False
        git(work, "checkout", "-q", "--detach", "origin/%s" % d)
        git(work, "checkout", head, "--", *files)
        git(work, "commit", "-q", "-m", "Zapis cyklu z niedokończonej sesji: %s" % ", ".join(files), check=False)
        if git(work, "push", "origin", "HEAD:refs/heads/%s" % d, check=False).returncode == 0:
            return True
    return False


def spawn_successor(n, i, report_body):
    m = re.search(r"^## Następca\s*\ntytuł:\s*(.+)\ntreść:\s*(.*?)(?=^## |\Z)", report_body, re.S | re.M)
    if not m:
        return None
    labels = label_names(i)
    gen = max([int(l.split(":")[1]) for l in labels if l.startswith("pokolenie:")] or [0])
    if gen >= MAX_GEN:
        return None
    keep = [l for l in labels if l.startswith(("rola:", "model:", "effort:", ITER))] + ["pokolenie:%s" % (gen + 1)]
    body = m.group(2).strip() + "\n\n<!-- start-branch: task/%s -->\n" % n
    args = ["issue", "create", "--title", m.group(1).strip(), "--body-file", "-"]
    for l in keep:
        args += ["--label", l]
    url = gh(*args, inp=body).strip()
    s = int(url.rsplit("/", 1)[1])
    sid = issue(s)["id"]
    # następca dziedziczy blokady rodzica: to, co czekało na rodzica, czeka teraz na niego
    for dep in api_list("repos/%s/issues/%s/dependencies/blocking" % (REPO, n)):
        api("repos/%s/issues/%s/dependencies/blocked_by" % (REPO, dep["number"]), "issue_id=%s" % sid, method="POST")
    return s


def close_out(n, i, status, upd, prose):
    body = update_report(n, dict(upd, status=status), prose)
    edit_labels(n, add=["report:unread"], remove=["blocked:rate-limit", "conflict"])
    succ = spawn_successor(n, i, body) if status == "partial" else None
    gh("issue", "close", str(n), "--reason", "completed" if status == "done" else "not planned", check=False)
    if status == "done":
        unblock(n)
    elif not succ:     # następca przejął krawędzie rodzica: konsumenci czekają na niego
        halt_dependents(n, status)
    if succ:
        launch(succ)


def finalize(n, work):
    tmp = os.environ.get("RUNNER_TEMP", "/tmp")
    role = os.environ["ROLE"]
    i = issue(n)
    labels = label_names(i)
    publish(n, os.path.join(work, ".session", "report.md"))
    cur = find_report(n)
    f = fields(cur["body"]) if cur else {}
    status = f.get("status", "")
    exit_path = os.path.join(tmp, "agent-exit")
    exit_code = ""
    if os.path.exists(exit_path):
        with open(exit_path) as fh:
            exit_code = fh.read().strip()
    cause, limited, reset = machine_cause(os.path.join(tmp, "claude-execution-output.json"), exit_code)
    upd, prose = {"przyczyna": cause or None}, ""
    if role == "bench":
        ok = exit_code == "0"
        status, prose = ("done", "Benchmark policzony.") if ok else ("crashed", "Job benchmarku padł.")
    elif status not in AGENT_STATUSES:
        status = "paused" if limited else "crashed"
        prose = ("Limit subskrypcji; wznowienie zaplanowane." if limited
                 else "Agent nie zostawił statusu terminalnego (%s)." % (cause or "bez przyczyny"))
    if role == "bench":
        commit_bench(n, work)   # krok bench zabity limitem czasu nie zdążył scommitować
    # nic z gałęzi nie ginie z runnerem
    if git(work, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0:
        git(work, "push", "-f", "origin", "HEAD:refs/heads/task/%s" % n, check=False)
        sha = git(work, "rev-parse", "--short", "HEAD").stdout.strip()
        if status in AGENT_STATUSES | {"paused"} and role != "bench":
            upd["commit"] = f.get("commit", sha)
    if status == "done" and role != "bench":
        ok, out = run_verification(work, i["body"])
        if not ok:
            status, prose = "partial", "Epilog uruchomił `## Weryfikacja` i dostał błąd:\n```\n%s\n```" % out
            upd["weryfikacja"] = "fail"
    if status == "done":
        result, out = merge_main(n, role, work)
        if result == "conflict":
            k = int(f.get("konflikty", 0)) + 1
            upd["konflikty"] = k
            if k < MAX_CONFLICTS:
                update_report(n, dict(upd, status="partial"), "Rebase na gałąź domyślną: konflikt (próba %s)." % k)
                edit_labels(n, add=["conflict"])
                launch_again(n)
                return
            status, prose = "crashed", "Konflikt przy rebase %s razy z rzędu." % k
        elif result == "protected":
            status, prose = "blocked", "Zmiana dotyka chronionych ścieżek: %s. Scalenie odrzucone." % out
        elif result == "tests":
            status, prose = "partial", "Testy po rebase na gałąź domyślną czerwone:\n```\n%s\n```" % out
    if status != "done" and status != "paused" and role != "bench":
        merge_notes(work)
    if status == "paused":
        k = int(f.get("proby", 0)) + 1
        age = (now() - parse_time(i["created_at"])).days
        if k > MAX_ATTEMPTS or age >= MAX_AGE_DAYS:
            status, prose = "crashed", "Wznowień wyczerpano (%s) albo wiek issue %s dni." % (k, age)
        else:
            when = reset or now() + timedelta(hours=BACKOFF_H[min(k - 1, len(BACKOFF_H) - 1)])
            update_report(n, dict(upd, status="paused", proby=k, wznow_po=when.strftime("%Y-%m-%dT%H:%M:%SZ")), prose)
            edit_labels(n, add=["blocked:rate-limit"])
            # zegar w workflow: cron GitHuba spóźnia się o godziny, a park ma termin co do minuty
            gh("workflow", "run", "resume.yml", "-f", "issue=%s" % n, check=False)
            return
    ahead = git(work, "rev-list", "--count", "origin/%s..HEAD" % os.environ.get("DEFAULT_BRANCH", "main"), check=False).stdout.strip()
    if status != "done" and ahead not in ("", "0"):
        # scommitowana praca nie ginie, tylko czeka: orchestrator wskazuje ją następcy
        prose += ("\n\nPraca zostaje na `task/%s` (%s commitów ponad gałąź domyślną). Następca startuje z niej, "
                  "gdy ma w treści `<!-- start-branch: task/%s -->`." % (n, ahead, n))
    close_out(n, i, status, upd, prose)


def launch_again(n):
    # konflikt nie jest porażką zadania: to samo issue, ponownie
    launch(n)


# ---------------------------------------------------------------- dozorca

def open_awaria(title, why, todo):
    body = "## Co stoi\n\n%s\n\n## Czego próbowałem\n\nDozorca: sztywny skrypt, bez agenta. Kopnięcia nie dały przebiegu albo sonda padła.\n\n## Co masz zrobić ty\n\n%s\n" % (why, todo)
    gh("issue", "create", "--title", "AWARIA: " + title, "--label", "awaria", "--body-file", "-", inp=body)


def awaria_open():
    awarie = json.loads(gh("issue", "list", "--label", "awaria", "--state", "open", "--json", "number") or "[]")
    if awarie:
        say("cisza: awaria otwarta #%s" % awarie[0]["number"])     # jedyny stan, w którym brak przebiegów nie jest zatorem
    return bool(awarie)


def watch():
    if not guard_ok() or awaria_open():
        return 0
    red = False
    code = probe()
    if code in (401, 403):
        open_awaria("martwe poświadczenie Claude (HTTP %s)" % code,
                    "Sonda `CLAUDE_CODE_OAUTH_TOKEN` zwróciła %s. Żadna sesja nie wstanie." % code,
                    "Wygeneruj nowy token (`claude setup-token`) i zapisz jako sekret repo. Potem zdejmij etykietę `awaria`.")
        say("awaria: martwe poświadczenie Claude (HTTP %s)" % code)
        return 1     # czerwony przebieg z crona = mail do autora pliku workflow
    assets = subprocess.run(["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-H",
                             "Authorization: Bearer " + os.environ.get("ASSETS_READ_TOKEN", ""),
                             "https://api.github.com/repos/Kucze3205/blockblast-assets"],
                            capture_output=True, text=True).stdout
    if assets in ("401", "403", "404"):
        say("ASSETS_READ_TOKEN martwy (%s): sam mail, bez awarii — gatuje tylko verifiera" % assets)
        red = True
    return drive() or (1 if red else 0)


def reconcile():
    """Koniec każdej sesji: pętla bez zobowiązań rusza od razu, nie przy następnym cronie (ten spóźnia się o godziny)."""
    if guard_ok() and not awaria_open():
        drive()


def drive():
    """Wspólny ogon dozorcy i epilogu: seria padów -> awaria; zaparkowane po terminie -> wznów; brak zobowiązań -> kopnij."""
    if crash_streak():
        open_awaria("%s sesje z rzędu padły bez commita" % CRASH_STREAK,
                    "Trzy ostatnie sesje zakończyły się `crashed` bez commita. Licznik jest ślepy na przyczynę.",
                    "Obejrzyj przyczynę maszynową w raportach ostatnich sesji (pole `przyczyna`) i napraw.")
        say("awaria: %s sesje z rzędu padły bez commita" % CRASH_STREAK)
        return 1
    watch_parked()
    if commitments():
        say("cisza: zobowiązania w toku")
        return 0
    return kick()


def crash_streak():
    # seria liczy się od zamknięcia ostatniej awarii: te same pady nie otwierają jej drugi raz
    awarie = json.loads(gh("issue", "list", "--label", "awaria", "--state", "closed", "--json", "closedAt", "--limit", "5") or "[]")
    since = max((a["closedAt"] for a in awarie), default="")
    closed = [x for x in api_list("repos/%s/issues?state=closed&sort=updated&direction=desc&per_page=30&labels=report:unread" % REPO)
              if x["closed_at"] > since
              and any(l["name"].startswith("rola:") and l["name"] != "rola:bench" for l in x["labels"])]
    if len(closed) < CRASH_STREAK:
        return False
    for x in closed[:CRASH_STREAK]:
        r = find_report(x["number"])
        f = fields(r["body"]) if r else {}
        if f.get("status") != "crashed" or f.get("commit"):
            return False
    return True


def parked_until(n):
    """`wznow_po` bieżącego parku albo None, gdy issue już nie jest zaparkowane."""
    if "blocked:rate-limit" not in label_names(issue(n)):
        return None
    r = find_report(n)
    return fields(r["body"]).get("wznow_po") if r else None


def resume(n):
    """Śpi do `wznow_po` i wznawia zaparkowane issue. Powtórka dozorcy jest nieszkodliwa: launch deduplikuje.
    Po przebudzeniu park musi być ten sam: nowy park (inny termin) ma własny przebieg resume z epilogu."""
    r = find_report(n)
    due = fields(r["body"]).get("wznow_po") if r else None
    if not due:
        say("#%s: brak wznow_po, wznowienie zostaje dozorcy" % n)
        return
    wait = (parse_time(due) - now()).total_seconds()
    if wait > MAX_SLEEP_S:
        # termin dalej niż limit joba: śpij, ile wolno, i przekaż zegar następnemu przebiegowi
        say("#%s: termin %s poza limitem joba, śpię %s s i przekazuję zegar dalej" % (n, due, MAX_SLEEP_S))
        time.sleep(MAX_SLEEP_S)
        if parked_until(n) == due:
            gh("workflow", "run", "resume.yml", "-f", "issue=%s" % n, check=False)
        return
    if wait > 0:
        say("#%s: śpię %s s do %s" % (n, int(wait), due))
        time.sleep(wait)
    if parked_until(n) == due and launch(n):
        say("#%s: wznowiono o czasie" % n)


def watch_parked():
    for x in api_list("repos/%s/issues?state=open&labels=blocked:rate-limit" % REPO):
        r = find_report(x["number"])
        f = fields(r["body"]) if r else {}
        age = (now() - parse_time(x["created_at"])).days
        if age >= MAX_AGE_DAYS:
            os.environ["ROLE"] = "-"
            close_out(x["number"], x, "crashed", {"przyczyna": "zapadka-wieku"}, "Zapadka wieku: %s dni." % age)
            continue
        due = f.get("wznow_po")
        if due and parse_time(due) <= now():
            launch(x["number"])
    return False


def loop_open():
    """Jedyne źródło issues dla dozorcy i zobowiązań: bez `loop:iteration N` pętla issue nie widzi."""
    return [x for x in api_list("repos/%s/issues?state=open" % REPO)
            if "pull_request" not in x and in_loop({l["name"] for l in x["labels"]})]


def commitments():
    """Pętla żyje <=> istnieje zobowiązanie: przebieg w toku, park z terminem w przyszłości, świeży dispatch."""
    if LAUNCHED:
        return True
    runs = session_runs()
    if any(r["status"] in ("queued", "in_progress", "waiting") for r in runs):
        return True
    recent = {run_issue(r["displayTitle"]) for r in runs if now() - parse_time(r["createdAt"]) < timedelta(minutes=GRACE_MIN)}
    for x in loop_open():
        names = label_names(x)
        r = find_report(x["number"])
        f = fields(r["body"]) if r else {}
        if "blocked:rate-limit" in names and f.get("wznow_po") and parse_time(f["wznow_po"]) > now():
            return True
        if "session #%s" % x["number"] in recent:
            return True
    return False


def kick():
    """Zator: kopnij, zanim zawołasz. Bezskuteczne kopnięcia liczy raport issue."""
    ready = [x for x in loop_open() if is_unblocked(x["number"])
             and "blocked:rate-limit" not in label_names(x)]
    if not ready:
        # czysta śmierć: zero otwartych issues to zator, nie sukces. Nowy orchestrator ze sztywnego szablonu.
        it = ITER + str(last_iteration() + 1)
        ensure_label(it)
        url = gh("issue", "create", "--title", "Cykl orchestratora wznowiony przez dozorcę", "--label", "rola:orchestrator", "--label", it,
                 "--body-file", "-", inp="## Cel\n\nPętla zatrzymała się bez otwartych issues. Przeczytaj najnowszy `docs/journal/cykl-*.md` (sekcja `## Stan`) i zbuduj następną mapę.\n\n"
                 "## Kryteria akceptacji\n\n- [ ] wpis dziennika i mapa zadań z rolami i krawędziami\n\n## Kontekst\n\n`docs/loop-config.md`\n").strip()
        ready = [issue(int(url.rsplit("/", 1)[1]))]
        say("pętla pusta: nowy orchestrator %s" % url)
    for x in ready[:12]:
        n = x["number"]
        r = find_report(n)
        f = fields(r["body"]) if r else {}
        k = int(f.get("kopniecia", 0)) + 1
        if k > MAX_KICKS:
            open_awaria("dozorca kopnął #%s %s razy, przebieg nie powstał" % (n, MAX_KICKS),
                        "Dispatch nie tworzy przebiegu (zepsuty workflow, odrzucone wywołanie, zdarzenie zgubione).",
                        "Sprawdź `.github/workflows/`, zakładkę Actions i uprawnienia tokenu.")
            say("awaria: dozorca kopnął #%s %s razy, przebieg nie powstał" % (n, MAX_KICKS))
            return 1
        update_report(n, {"kopniecia": k, "kopniete": now().strftime("%Y-%m-%dT%H:%M:%SZ")})
        if launch(n):
            say("kopnięto #%s" % n)
    return 0


# ---------------------------------------------------------------- main

def main(argv):
    cmd, args = argv[1], argv[2:]
    if cmd == "guard":
        return 0 if guard_ok() else 10
    if cmd == "probe":
        code = probe()
        print("sonda: HTTP %s" % code)
        return 1 if code in (401, 403) else 0
    if cmd == "route":
        if not guard_ok():
            return 0
        launch(int(args[0]))
        return 0
    if cmd == "export":
        export(int(args[0]), args[1])
        return 0
    if cmd == "publish":
        publish(int(args[0]), args[1])
        return 0
    if cmd == "finalize":
        finalize(int(args[0]), args[1])
        reconcile()
        return 0
    if cmd == "bench":
        bench(int(args[0]), args[1])
        return 0
    if cmd == "watch":
        return watch()
    if cmd == "resume":
        resume(int(args[0]))
        return 0
    raise SystemExit("nieznane polecenie: " + cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
