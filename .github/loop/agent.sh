#!/usr/bin/env bash
# Sesja agenta odkrywczego. Agent pracuje w $WORK na gałęzi łańcucha (jedyny ref, bez remote'a);
# historia prób leży w $WORK/.historia, skill i subagent w ~/.claude, hook czasu w $RUNNER_TEMP.
# Checkoutu gałęzi pętli w tym czasie na dysku nie ma.
set -u
OUT="$RUNNER_TEMP"
cd "$WORK" || exit 1

PROMPT="Wywołaj skill \`implementer\` narzędziem Skill i popraw wynik agenta w grze. Historia prób: .historia/INDEKS.md. Pracujesz na gałęzi $GALAZ; commituj często."
if [ "$KONTYNUACJA" = 1 ]; then
  PROMPT="$PROMPT To kontynuacja przerwanej próby: jej dotychczasowe commity to \`git log -p $RODZIC_SHA..HEAD\`."
fi

# koniec tury w -p to koniec sesji: praca w tle ginie z runnerem
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
# poświadczenie zostaje w procesie Claude Code, znika z Basha i hooków
export CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1
# przeciążenia API (429/529) ponawiane zamiast końca sesji; to ponawia też limit subskrypcji, więc stream_filter.py
# sam kończy sesję na zdarzeniu rate_limit `rejected` (inaczej wisi do `timeout`, a loop.py nie widzi limitu)
export CLAUDE_CODE_RETRY_WATCHDOG=1
# trening na pierwszym planie: domyślnie Bash ucina po 2 min
export BASH_DEFAULT_TIMEOUT_MS=$((SESJA_MIN * 60000)) BASH_MAX_TIMEOUT_MS=$((SESJA_MIN * 60000))
export KONIEC=$(( $(date +%s) + SESJA_MIN * 60 ))

timeout "${SESJA_MIN}m" claude -p "$PROMPT" \
  --model claude-sonnet-5-5 --effort medium \
  --permission-mode acceptEdits \
  --allowedTools "Read,Edit,Write,Glob,Grep,Skill,Agent,WebSearch,WebFetch,Bash(git *),Bash(python *),Bash(python3 *),Bash(pytest *),Bash(pip install *)" \
  --disallowedTools Monitor \
  --settings "$OUT/ustawienia.json" \
  --max-turns 150 --output-format stream-json --verbose \
  2> "$OUT/claude-stderr.txt" \
  | python3 "$OUT/stream_filter.py" "$OUT"
echo "${PIPESTATUS[0]}" > "$OUT/agent-exit"
exit 0
