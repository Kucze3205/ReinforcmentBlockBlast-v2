#!/usr/bin/env python3
"""Podgląd sesji na żywo (#69): stdin = NDJSON z `claude --output-format stream-json --verbose`.
Log kroku jest publiczny: bez tool_result i thinking. Nigdy nie kończy się błędem i zawsze drenuje stdin
(pad filtra = SIGPIPE dla agenta). Do $1 zapisuje stream.ndjson i claude-execution-output.json (tylko `result`,
bo machine_cause w loop.py parsuje ten plik jako jeden obiekt JSON)."""
import json
import os
import sys


def show(ev):
    if ev.get("type") != "assistant":
        return
    for b in ev.get("message", {}).get("content", []):
        if b.get("type") == "text":
            print("💬 " + b["text"].strip()[:300], flush=True)
        elif b.get("type") == "tool_use":
            i = b.get("input", {})
            arg = i.get("command") or i.get("file_path") or i.get("pattern") or i.get("path") or json.dumps(i, ensure_ascii=False)
            print("🔧 %s %s" % (b.get("name"), str(arg).replace("\n", " ")[:150]), flush=True)


def main(out):
    result = None
    with open(os.path.join(out, "stream.ndjson"), "w") as raw:
        for line in sys.stdin:
            raw.write(line)
            try:
                ev = json.loads(line)
                if ev.get("type") == "result":
                    result = ev
                    print("✅ tury=%s koszt=$%s błąd=%s" % (ev.get("num_turns"), ev.get("total_cost_usd"), ev.get("is_error")), flush=True)
                else:
                    show(ev)
            except Exception:
                pass
    if result is not None:
        with open(os.path.join(out, "claude-execution-output.json"), "w") as fh:
            json.dump(result, fh)


if __name__ == "__main__":
    try:
        main(sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RUNNER_TEMP", "/tmp"))
    except BaseException:
        for _ in sys.stdin:
            pass
    sys.exit(0)
