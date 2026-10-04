#!/usr/bin/env bash
# Faza offline: M kolejnych sesji, każda pisze wersję polityki, runner liczy jej V na zapisanych drzewach.
# Sesja widzi tylko katalog $META (kandydat, archiwum wersji, baseline, manifesty drzew, opis zadania):
# bez Basha i internetu, bez tokenu GitHuba w środowisku, poświadczenie tylko w procesie Claude Code.
# Użycie (z checkoutu gałęzi domyślnej): offline.sh <drzewo>
set -eu
T=$1
RUN="$RUNNER_TEMP/offline"
META="$RUNNER_TEMP/meta"
OFFLINE="python3 .github/loop/offline.py"
SESJA_MIN=80   # sufit jednej sesji; M razy tyle musi się zmieścić w jobie

export CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1
export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
export CLAUDE_CODE_RETRY_WATCHDOG=1

sesja() {
  OUT="$RUNNER_TEMP/sesja-$1"
  mkdir -p "$OUT"
  (cd "$META" && timeout "${SESJA_MIN}m" claude -p "Przeczytaj ZADANIE.md i wykonaj je." \
    --model claude-sonnet-5-5 --effort high \
    --permission-mode acceptEdits \
    --disallowedTools "Bash,WebSearch,WebFetch,Agent,Monitor" \
    --max-turns 80 --output-format stream-json --verbose \
    2> "$OUT/claude-stderr.txt" \
    | python3 "$RUNNER_TEMP/stream_filter.py" "$OUT"
    echo "${PIPESTATUS[0]}" > "$OUT/agent-exit") || true
}

$OFFLINE init "$T" "$RUN"
M=$($OFFLINE ile)
for m in $(seq 1 "$M"); do
  echo "::group::wersja $m z $M"
  $OFFLINE meta "$m" "$RUN" "$META"
  sesja "$m"
  # limit subskrypcji: jedno czekanie do resetu (najwyżej 4 h), potem ta sama sesja jeszcze raz
  s=$(python3 .github/loop/loop.py limit "$RUNNER_TEMP/sesja-$m/claude-execution-output.json" "$(cat "$RUNNER_TEMP/sesja-$m/agent-exit" 2>/dev/null || echo brak)")
  if [ "$s" -gt 0 ] && [ "$s" -le 14400 ]; then
    echo "limit subskrypcji, czekam ${s}s"
    sleep "$s"
    sesja "$m"
  fi
  $OFFLINE wynik "$m" "$RUN" "$META"
  echo "::endgroup::"
done
$OFFLINE wybierz "$T" "$RUN" | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"
