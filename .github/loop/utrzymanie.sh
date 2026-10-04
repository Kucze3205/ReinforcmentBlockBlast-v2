#!/usr/bin/env bash
# Utrzymanie ewaluatora: agent naprawia most i kalibruje symulator, skrypt sprawdza. Dwa tryby:
#   petla    do $ITERACJE iteracji "sesja agenta -> sprawdzenie"; wynik w $WYNIK (status, naprawa.patch, iteracje.md)
#   sprawdz  testy silnika i mostu, odcinek na emulatorze, bramka kalibracji (to samo odpala agent: .zadanie/sprawdz.sh)
# Środowisko: ZAUFANE (kopia .github z gałęzi domyślnej, poza zasięgiem agenta), WORK (kod do naprawy, własne repo
# bez remote'a), WYNIK, POWOD, ID, ITERACJE, ITERACJA_MIN; dla `petla` też CLAUDE_CODE_OAUTH_TOKEN.
# Bramka jest z ZAUFANE: agent może zmienić tylko pliki z `kalibracja.py sciezki`, nie sprawdzenie.
set -u
export PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1   # polskie znaki w logach i notatkach niezależnie od ustawień systemu
KAL="$ZAUFANE/.github/evaluator/kalibracja.py"
SCIEZKI=$(python3 "$KAL" sciezki | tr -d '\r')   # Python na Windowsie kończy linie CRLF
ODCINEK=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['kalibracja']['odcinek_ruchy'])" "$ZAUFANE/.github/evaluator/config.json")

sprawdz() {
  cd "$WORK" || return 1
  mkdir -p "$WYNIK"
  # testy silnika i mostu idą z kodem naprawy; kod naprawy nie widzi poświadczenia
  if ! python3 -m unittest tests.test_engine tests.test_bridge > "$WYNIK/testy.txt" 2>&1; then
    echo "Testy silnika i mostu nie przechodzą:"; tail -30 "$WYNIK/testy.txt"; return 1
  fi
  rm -rf bridge-out
  ( unset CLAUDE_CODE_OAUTH_TOKEN; MOVES=$ODCINEK CEL=0 LIMIT_MINUT=20 bash tools/bridge.sh ) > "$WYNIK/odcinek.log" 2>&1
  python3 "$KAL" bramka --kod "$WORK" --odcinek "$WORK/bridge-out" --out "$WYNIK/bramka.json"
}

zadanie() {
  # $1 = numer iteracji; poprzednie próby i ostatnia bramka są w treści
  {
    echo "# Zadanie: most i symulator"
    echo
    echo "Powód: \`$POWOD\` (\`faza0\` = pierwsza kalibracja symulatora do logów mostu; \`most\` = partia przerwana"
    echo "albo unieważniona na emulatorze; \`rozjazd\` = symulator odbiega od licznika apki albo od rozkładu klocków)."
    echo "Iteracja $1 z $ITERACJE. Czas iteracji: $ITERACJA_MIN min."
    echo
    echo "## Co wolno"
    echo
    echo "Zmieniasz tylko: $(echo $SCIEZKI)"
    echo "Zmiana czegokolwiek innego unieważnia naprawę."
    echo
    echo "## Kryterium"
    echo
    echo "\`bash .zadanie/sprawdz.sh\` (kilka–kilkanaście minut): testy silnika i mostu, odtworzenie logów zestawu"
    echo "kontrolnego (\`.github/evaluator/kalibracja/zestaw/\`) w symulatorze i odcinek $ODCINEK ruchów na emulatorze."
    echo "Miary: tempo punktów (te same ruchy w symulatorze dają sumę punktów w ±15% od licznika apki) i rozkład"
    echo "klocków (χ², p ≥ 0,01). Miar i progów nie zmieniasz."
    echo
    echo "## Dane"
    echo
    echo "\`.zadanie/dane/\`: logi serii, która otworzyła zadanie (\`moves.jsonl\`, \`pomiar.json\`, \`logcat.txt\`, \`install.txt\`)"
    echo "i jej miary (\`rozjazd.json\`), o ile istnieją."
    if [ -s "$WYNIK/iteracje.md" ]; then
      echo
      echo "## Poprzednie iteracje"
      echo
      cat "$WYNIK/iteracje.md"
    fi
  } > "$WORK/.zadanie/ZADANIE.md"
}

sesja() {
  # $1 = numer iteracji; sekundy do końca limitu subskrypcji (0 = sesja się odbyła) trafiają do $out/limit-s
  local out="$WYNIK/iteracja-$1"
  mkdir -p "$out"
  export KONIEC=$(( $(date +%s) + ITERACJA_MIN * 60 ))
  export CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1 CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1 CLAUDE_CODE_RETRY_WATCHDOG=1
  export BASH_DEFAULT_TIMEOUT_MS=$((ITERACJA_MIN * 60000)) BASH_MAX_TIMEOUT_MS=$((ITERACJA_MIN * 60000))
  cd "$WORK" || return 1
  CLAUDE_CODE_OAUTH_TOKEN=$TOKEN timeout "${ITERACJA_MIN}m" claude -p \
    "Wywołaj skill \`utrzymanie\` narzędziem Skill. Zadanie: .zadanie/ZADANIE.md (iteracja $1 z $ITERACJE)." \
    --model claude-sonnet-5-5 --effort medium \
    --permission-mode acceptEdits \
    --allowedTools "Read,Glob,Grep,Skill,WebSearch,WebFetch,Bash(git *),Bash(python *),Bash(python3 *),Bash(bash .zadanie/*)" \
    --disallowedTools Monitor \
    --settings "$ZAUFANE/ustawienia.json" \
    --max-turns 120 --output-format stream-json --verbose \
    2> "$out/claude-stderr.txt" \
    | python3 "$ZAUFANE/.github/loop/stream_filter.py" "$out"
  echo "${PIPESTATUS[0]}" > "$out/agent-exit"
  python3 "$ZAUFANE/.github/loop/loop.py" limit "$out/claude-execution-output.json" "$(cat "$out/agent-exit")" > "$out/limit-s"
}

petla() {
  TOKEN=${CLAUDE_CODE_OAUTH_TOKEN:-}
  unset CLAUDE_CODE_OAUTH_TOKEN   # od tej chwili poświadczenie ma tylko proces claude
  mkdir -p "$WYNIK"
  cd "$WORK" || exit 1
  local baza i=1 czekano=0 czeka
  baza=$(git rev-parse HEAD)
  echo nieudane > "$WYNIK/status"
  : > "$WYNIK/iteracje.md"
  while [ "$i" -le "$ITERACJE" ]; do
    zadanie "$i"
    sesja "$i"
    czeka=$(cat "$WYNIK/iteracja-$i/limit-s" 2>/dev/null || echo 0)
    if [ "${czeka:-0}" -gt 0 ] && [ "$czeka" -le 7200 ] && [ "$czekano" -lt 2 ]; then
      echo "limit subskrypcji: czekam ${czeka}s, iteracja $i się nie liczy"
      czekano=$((czekano + 1)); sleep "$czeka"; continue
    fi
    cd "$WORK" && git add -A && git commit -q -m "Utrzymanie: niezatwierdzone zmiany iteracji $i" 2>/dev/null
    local zle
    zle=$(git diff --name-only "$baza" HEAD | python3 "$KAL" dozwolone)
    sprawdz > "$WYNIK/sprawdzenie-$i.txt" 2>&1; local kod=$?
    {
      echo "### Iteracja $i"
      [ -n "$zle" ] && echo "Zmienione pliki spoza dozwolonych (cofnij je): $(echo "$zle" | tr '\n' ' ')"
      tail -8 "$WYNIK/sprawdzenie-$i.txt"
      echo
    } >> "$WYNIK/iteracje.md"
    if [ "$kod" -eq 0 ] && [ -z "$zle" ]; then echo przeszla > "$WYNIK/status"; break; fi
    i=$((i + 1))
  done
  cd "$WORK" && git diff "$baza" HEAD -- $SCIEZKI > "$WYNIK/naprawa.patch"
}

case "${1:-}" in
  petla) petla ;;
  sprawdz) sprawdz ;;
  *) echo "użycie: utrzymanie.sh petla|sprawdz" >&2; exit 2 ;;
esac
