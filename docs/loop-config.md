# Konfiguracja pętli — sekrety, zmienne, uprawnienia

Kontrakt nazw między workflowami a sesjami. Workflow, który odwołuje się do nazwy
spoza tej listy, jest błędem — nie okazją do dopisania nowej nazwy bez decyzji.

Sekcje o pozostałych workflowach powstaną razem z nimi.

---

## Sekrety

| Nazwa | Przeznaczenie |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Uwierzytelnia sesje Claude Code subskrypcją właściciela. Powstaje z `claude setup-token`, ważny rok. |
| `ASSETS_READ_TOKEN` | Odczyt wydania z APK z prywatnego repo zasobów (`gh release download`). Wygasa ok. 2026-10-21. |
| `DEALS_SALT` | Sól rozdań oceny symulatorem (`ocena.py`): rozdania drzewa to `random.Random("<sól>:<drzewo>")`. Widzi ją tylko krok `sym` w `ocena.yml`; proces zabiera ją ze środowiska, zanim zaimportuje kod węzła. Brak soli to błąd, nie wartość domyślna (repo jest publiczne). Ustawienie: `gh secret set DEALS_SALT --body "$(python -c 'import secrets;print(secrets.token_hex(16))')"`. Zmiana soli zmienia hash i unieważnia `s_sym` wszystkich węzłów. |

Do samowyzwalania pętli **nie ma sekretu** — wystarcza wbudowany `GITHUB_TOKEN`
w parze z `workflow_dispatch`. Żadnego PAT-a, żadnego klucza GitHub App.

Wygaśnięcie obu tokenów to notatka dla właściciela — pętla dat nie czyta.

### `ANTHROPIC_API_KEY` — zakaz

Ta nazwa **nie może istnieć** ani jako sekret, ani jako zmienna, ani w `env:`
żadnego joba. Ma udokumentowane pierwszeństwo nad tokenem subskrypcji i cicho
przekieruje rachunek na płatne API. Cisza jest tu najgorsza — nic się nie zepsuje,
tylko przyjdzie faktura.

---

## Ewaluator (`ocena.yml`, `seria.yml`, `.github/evaluator/`)

Ocena węzła: `gh workflow run ocena.yml -f wezel=<sha> -f drzewo=<t> -f id=<nazwa>`.
Przebieg: 10 shardów symulatora (300 rozdań, cap 2000) → przy 0 przegranych seria 10 partii na
emulatorze (`seria.yml`, jedna naraz: `concurrency: seria`) → artefakt `ocena-<id>` z `ocena.json`.
Pierwszy krok pętli, `AUTOPILOT`, sprawdza `ocena.yml`; `seria.yml` wywołana z niego już go nie sprawdza.

| Co | Zasada |
|---|---|
| `s_sym` | przeżycie/cap średnio po rozdaniach, punkty tylko rozstrzygają remis (waga `tie` ≪ 1/cap), nie więcej niż 1 |
| `s_v` | `1 + s_emu` przy pełnej serii, inaczej `s_sym`; liczy `ocena.s_v()`, nie jest zapisywane |
| próg serii | 0 przegranych w symulatorze i ocena nie „za wolna" (shard przekroczył `limit_shardu_s`) |
| partia serii | `pomiar.json` z mostu: `koniec` = `cel` \| `przegrana` \| `przerwanie` \| `awaria`; ważne tylko dwie pierwsze |
| powtórka | brakujące numery partii (`partie`), wynik scala `ocena.py zlicz --poprzednia`; do pełnych 10 ważnych status to `w_toku` |
| bramka celu | `ocena.py bramka ocena.json`: 10 ważnych partii, wszystkie `cel`; kod 0 = cel osiągnięty ; `ocena.yml` zakłada wtedy `trees/cel.json` — znacznik końca pętli, który ma sprawdzać harmonogram drzewa |
| hash | `sym` (symulator, generator, punktacja, `ocena.py`, parametry, rozdania drzewa) i `most` (most, `seria.yml`, liczba partii i cel); naprawa mostu nie przelicza `s_sym` |
| tylko do odczytu | pliki z `tylko_do_odczytu` w `config.json`: ewaluator nakłada je z gałęzi domyślnej na kopię węzła |
| rekord węzła | `ocena.yml` dopisuje do `oceny` (`s_sym` per hash, `sym` z przeżyciem per rozdanie, `emu` z wynikami partii i unieważnionymi, `hash_most`; `czas_sym_min` raz, z pierwszej oceny; `s_emu` i `czas_serii_min` dopiero przy pełnej serii) i ustawia `stan`: `oceniony` albo `ocena w toku`; `oczekiwanie_min` zostaje po stronie wywołującego |
| polityka węzła | `policies.build(weights)`; wagi z katalogu `weights/` węzła (`.gitignore` przepuszcza tam `*.pth`) |

---

## Zmienne repo

| Nazwa | Wartość | Przeznaczenie |
|---|---|---|
| `AUTOPILOT` | `on` \| cokolwiek innego | Przełącznik właściciela. Pierwszy krok **każdego** workflow pętli. |

Warunek jest jawnie fail-safe: pętla rusza **wyłącznie** przy dosłownym `on`.
Brak zmiennej, literówka, pusta wartość — wszystko to znaczy „stój".

```yaml
if: vars.AUTOPILOT == 'on'
```

**Czego `AUTOPILOT` nie potrafi:** pętla nie może go przestawić sama. Klucz
`permissions` nie zna zakresu pozwalającego zapisać zmienną repo. To
przełącznik człowieka, nie bezpiecznik. Stan awaryjny, który pętla ustawia sobie
sama, musi leżeć w pliku w repo albo w przypiętym issue.

---

## Uprawnienia

Domyślne uprawnienia workflow w repo są na minimum i mają takie zostać:

| Ustawienie | Wartość |
|---|---|
| `default_workflow_permissions` | `read` |
| `can_approve_pull_request_reviews` | `false` |

Druga pozycja to w UI checkbox **„Allow GitHub Actions to create and approve pull
requests"**. Nazwa mówi o zatwierdzaniu, ale jedna opcja gasi **dwie** rzeczy:
`GITHUB_TOKEN` nie może PR-a zatwierdzić **ani go otworzyć**. Pętla nie otwiera
PR-ów, więc checkbox zostaje wyłączony na stałe.

Skoro domyślne to `read`, **każdy workflow musi jawnie zadeklarować `permissions:`**
— tylko to, czego potrzebuje. `actions: write` pozwala wywołać `workflow_dispatch`
na samej pętli.

Osobno, niezależnie od `permissions:`: tryb automation Claude Code **nie nadaje
żadnych uprawnień narzędziowych**. Każdy job musi podać `--permission-mode` i pełną
listę `--allowedTools`.

---

## Ustawienia wyklikiwane ręcznie

Settings → Actions → General. Nie ma dla nich REST API, więc nie ma jak ich
sprawdzić z poziomu sesji — stan poniżej jest deklaracją właściciela, nie pomiarem.

| Ustawienie | Wymagane |
|---|---|
| Send write tokens to workflows from pull requests | **wyłączone** (repo jest publiczne) |
| Require approval for all external contributors | **włączone** (przebiegi z forków) |

Sekrety repo — w tym `CLAUDE_CODE_OAUTH_TOKEN` — i tak **nie są** przekazywane do
przebiegów z forkowych PR-ów.

---

## Gałąź pętli

**Gałąź pętli to gałąź domyślna repozytorium. Dziś `main`.** Nie są to dwa
pojęcia, które trzeba trzymać w zgodzie — to jedno pojęcie. Wymuszają to dwa
udokumentowane ograniczenia GitHuba, z których żadne nie ma obejścia:

| Ograniczenie | Skutek |
|---|---|
| *„Workflow runs cannot restore caches created for child branches or sibling branches"* — run czyta cache z własnej gałęzi **albo z domyślnej** | Cache nie przechodzi między gałęziami siostrzanymi; wspólne rzeczy (np. obraz emulatora) muszą leżeć w cache'u gałęzi domyślnej |
| Workflow na zdarzeniu `issues` odpala się **wyłącznie z pliku na gałęzi domyślnej**; `workflow_dispatch` jest na liście widoczny dopiero stamtąd | Workflowy muszą leżeć na gałęzi domyślnej |

Klucze cache muszą być nowe przy każdym zapisie (`<nazwa>-${{ github.run_id }}`)
i odczytywane przez `restore-keys`, bo wpis o danym kluczu jest niemutowalny.

### Nazwa nie jest wpisywana na sztywno

Workflow ustala gałąź pętli przez `github.event.repository.default_branch`,
nigdy przez literał `main`.

Powód jest jeden i wystarczający: **pętla nie może edytować `.github/workflows/`**
(akcja twardo tego zabrania). Nazwa wpisana na sztywno byłaby jedyną rzeczą, której
pętla nie umie naprawić, umieszczoną w jedynym miejscu, którego nie umie tknąć.

---

## Drzewo na żywo — `drzewo.yml`, `.github/policy/`, `.github/loop/drzewo.py`

```bash
gh variable set AUTOPILOT --body on
gh workflow run drzewo.yml        # start: bieżące otwarte drzewo albo następne po zamkniętym
```

Harmonogram jest zdarzeniowy: krótki job `krok` (grupa `polityka`, kroki idą po kolei) czyta `trees/`,
a dalej robi jedno z trzech: czeka (ostatnia paczka ma nieocenione węzły), otwiera następną paczkę
(commit `trees/<t>.json`, potem `wezel.yml` dla każdego jej węzła) albo zamyka drzewo. Wywołuje go
koniec oceny każdego węzła (`ocena.yml`, a dla węzła bez zmian `wezel.yml`). Krok bez zmian w drzewie
niczego nie robi, więc powtórzone wywołania są nieszkodliwe. Drzewa startują od tagu `korzen`.

| Plik | Co to |
|---|---|
| `.github/policy/config.json` | Konfiguracja właściciela, jedyne miejsce: `W` (paczka ≤ W węzłów naraz), `K` (rund na drzewo, wspólne dla drzewa na żywo i odtwarzania), `beta` (na godzinę), `M` (wersji w fazie offline). Zmiana `beta` zmienia definicję V; korekta `W`/`K` to commit właściciela, od następnego drzewa. |
| `.github/policy/policy.py` | Polityka: `solve(question)` zwraca paczkę. Pisze ją wyłącznie job wdrożenia, nigdy sesja LLM. Polityka startowa: pełne `W` łańcuchów od korzenia, potem kontynuacja każdego, aż `K` rund albo 2 kolejne węzły bez poprawy względem rodzica. |
| `trees/<t>.json` | Stan drzewa: `polityka` (skrót treści, przypięty na całe drzewo; zmiana w trakcie to błąd), `paczki` (nazwy węzłów w kolejności rund; kolejność utworzenia = pozycja po spłaszczeniu, od 1), `koniec` (`null` albo `powod`, `T_h`, `V`). |
| `trees/baseline.json` | Opcjonalny `{"s_v": x}` z fazy 0: punkt odniesienia dla węzłów od korzenia. Bez pliku baseline to 0. |

**Widok polityki (`question`).** `max_parallelism` (W), `max_rounds` (K), `round` (ukończone rundy),
`baseline_score`, `observed()` (ocenione węzły: `wezel`, `lancuch`, `glebokosc`, `rodzic`, `s_v`,
`delta` względem rodzica), `legal_actions()` (`None` = nowy łańcuch od korzenia; czubki łańcuchów).
Akcja `None` otwiera łańcuch od korzenia, nazwa czubka kontynuuje jego łańcuch. Maszyneria odrzuca
akcje niedozwolone, liść bierze najwyżej raz i obcina paczkę do `W`. Pusta paczka kończy drzewo.
Odtwarzanie nagranego drzewa używa tych samych `Pytanie`, `paczka`, `nazwij`, `czas_h` i `wartosc`
z `drzewo.py`; różni się tylko tym, że ujawnia zapisane rekordy zamiast uruchamiać węzły.

**Czas.** Koszt węzła w godzinach = `koszt.minuty` (sesja) + `oceny.czas_sym_min` + `oceny.czas_serii_min`;
`oczekiwanie_min` poza kosztem. Węzeł dziedziczony (kod bez zmian względem rodzica, nie korzenia) płaci
tylko za sesję. Paczka kosztuje najdłuższy z jej węzłów, `T` to suma po paczkach, `V = max s_v − beta·T`.
Seria jest jedna na paczkę z natury: partie idą równolegle, a paczka płaci za najdłuższy węzeł.

**Zamknięcie.** Powód: `pusta paczka`, `K` albo `cel` (obecność `trees/cel.json`). Po `pusta paczka`
i `K` krok dispatchuje `offline.yml -f drzewo=<t>`; ten workflow musi używać grupy `polityka`
(następne drzewo czeka, aż skończy) i na końcu wywołać `drzewo.yml` bez argumentu, co otwiera
następne drzewo. Po `cel` pętla się kończy: offline się nie odpala, nowe drzewo nie powstaje,
węzły w toku dokańczają się same.

---

## Węzeł — `wezel.yml`

```bash
gh workflow run wezel.yml -f drzewo=<t> -f wezel=<łańcuch>.<głębokość> -f kolejnosc=<n>
```

Jedna sesja agenta odkrywczego i jej rekord. Rodzicem `2.3` jest `2.2`, rodzicem `2.1`
korzeń. Dispatch nowego węzła wymaga ocenionego rodzica. Ten sam dispatch dla węzła
z rekordem w stanie `sesja` albo `zaparkowany` jest kontynuacją (`kolejnosc` ignorowana).

| Nazwa | Co to |
|---|---|
| tag `korzen` | Commit bez rodzica: kod projektu, `CONTEXT.md`, `tools/`, reguły gry. Bez `.claude/`, `.github/`, `bench/` i dokumentów pętli. Każdy łańcuch startuje stąd. |
| gałąź `trees/<t>/<łańcuch>` | Kod łańcucha. Pisze ją wyłącznie job węzła (push bez force po sesji); czubek to zawsze liść. |
| `trees/<t>/<węzeł>.json` na gałęzi pętli | Rekord węzła (niżej). Pisze go `zapisz.sh` z ponowieniami. |
| artefakt `transkrypt-<t>-<węzeł>-<run>-<próba>` | `stream.ndjson` sesji; z niego liczy się udział historii w oknie kontekstu. |

**Budżet:** job sesji 330 min, sesja 300 min (`timeout`), `--max-turns 150`. Po każdym narzędziu
hook dopisuje agentowi „Zostało X min sesji.”.

**Co widzi agent:** checkout `work/` z jednym refem (gałąź łańcucha), bez remote'a i bez
poświadczeń (`CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1`, token GitHuba tylko w krokach maszynerii);
`.historia/` (indeks, rekordy ocenionych węzłów, patche innych łańcuchów, poprzednie drzewa bez
kodu); skill `implementer` i subagent `researcher` skopiowane do `~/.claude`. Checkout gałęzi
pętli jest usuwany przed sesją i wraca po niej.

**Po sesji** (`loop.py koniec`):

| Następny krok | Kiedy | Co robi job |
|---|---|---|
| `park` | limit subskrypcji | `stan: zaparkowany`, `wznow_po` = reset z komunikatu albo +60 min; dispatch samego siebie, job `czekaj` śpi do `wznow_po` (dłużej niż ~5,75 h → dispatch kolejnego czekania) |
| `kontynuuj` | `error_max_turns`, pierwszy raz | dispatch samego siebie; drugi raz → `ocena` |
| `dziedzicz` | SHA = rodzic (nie korzeń) | `stan: oceniony`, `oceny` skopiowane od rodzica, bez oceny |
| `ocena` | w pozostałych przypadkach | `stan: ocena w toku`; `gh workflow run ocena.yml -f wezel=<sha> -f drzewo=<t> -f id=<t>-<węzeł>` |

### Rekord węzła

| Pole | Pisze | Znaczenie |
|---|---|---|
| `rodzic`, `rodzic_sha` | węzeł | nazwa rodzica (`korzen` dla głębokości 1) i jego SHA |
| `kolejnosc` | węzeł (z dispatchu) | kolejność utworzenia w drzewie, dla replayu |
| `sha` | węzeł | czubek gałęzi łańcucha po sesji |
| `stan` | węzeł, ocena | `sesja` → `zaparkowany` ↔ `sesja` → `ocena w toku` → `oceniony` (ostatnie przejście robi ocena) |
| `gist`, `notatki` | węzeł | komunikaty commitów węzła, najnowszy pierwszy; gist = pierwsza linia najnowszego |
| `koszt` | węzeł | `tury`, `usd`, `minuty` (czas jobów sesji od startu do zapisu, suma po kontynuacjach) |
| `oczekiwanie_min` | węzeł, ocena | czas zaparkowania na limicie; ocena dopisuje ponowienia i naprawy |
| `kontynuacje_tur`, `sesje` | węzeł | licznik kontynuacji po turach; lista sesji (start, koniec, tury, przyczyna) |
| `zaparkowano`, `wznow_po` | węzeł | tylko w stanie `zaparkowany` |
| `oceny` | ocena | `s_sym` (słownik: hash ewaluatora → wynik), `s_emu`, wyniki per partia, czas serii |

Statusu „nieudany” nie ma: każdy węzeł idzie do oceny.

---

## Sonda poświadczenia

```bash
curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models   -H "Authorization: Bearer $CLAUDE_CODE_OAUTH_TOKEN"   -H "anthropic-version: 2023-06-01" -H "anthropic-beta: oauth-2025-04-20"
# 200 żyje · 401 martwy · 403 odwołany
```

Brak odpowiedzi sieci to nie martwe poświadczenie.
