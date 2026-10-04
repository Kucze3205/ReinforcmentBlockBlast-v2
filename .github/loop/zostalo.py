#!/usr/bin/env python3
"""Hook PostToolUse sesji: po każdym narzędziu podaje agentowi, ile minut sesji zostało (KONIEC = epoka końca)."""
import json
import os
import time

left = max(0, int((int(os.environ["KONIEC"]) - time.time()) // 60))
print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                         "additionalContext": "Zostało %d min sesji." % left}}))
