# Konfiguracja pętli — sekrety, zmienne, etykiety, uprawnienia

Kontrakt nazw między workflowami a sesjami. Workflow, który odwołuje się do nazwy
spoza tej listy, jest błędem — nie okazją do dopisania nowej nazwy bez decyzji.

---

## Sekrety

| Nazwa | Przeznaczenie |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` | Jedyne poświadczenie generowane ręcznie. Uwierzytelnia sesje Claude Code subskrypcją właściciela. Powstaje z `claude setup-token`, ważny rok. |

Do samowyzwalania pętli **nie ma sekretu** — wystarcza wbudowany `GITHUB_TOKEN`
w parze z `workflow_dispatch`. Żadnego PAT-a, żadnego klucza GitHub App.

### `ANTHROPIC_API_KEY` — zakaz

Ta nazwa **nie może istnieć** ani jako sekret, ani jako zmienna, ani w `env:`
żadnego joba. Ma udokumentowane pierwszeństwo nad tokenem subskrypcji i cicho
przekieruje rachunek na płatne API. Cisza jest tu najgorsza — nic się nie zepsuje,
tylko przyjdzie faktura.

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

## Etykiety

Etykieta na issue wybiera zachowanie workflow. Jeden prefiks `rola:` dla wszystkiego,
co wybiera rolę; lista **nie jest zamknięta** — orchestrator dokłada nowe role jako
`rola:<nazwa>` bez tykania workflowów, bo rola to para skill + profil z `.claude/profiles.yml`.

| Etykieta | Znaczenie |
|---|---|
| `rola:orchestrator` | Planuje, tworzy issues, dispatchuje sesje. Jedyna rola tworząca issues. |
| `rola:implementer` | Zmienia kod. Bez internetu. |
| `rola:researcher` | Ma internet. Bez zapisu kodu. |
| `rola:verifier` | Emulator i most do oryginału. Jedyna rola z emulatorem. |
| `rola:bench` | Pseudo-rola: przebieg benchmarku, bez sesji agenta. |

### Nadpisania — lista zamknięta

Domyślnie Sonnet 5.5 (`claude-sonnet-5-5`) / effort medium. Etykietę nadaje **wyłącznie orchestrator**,
nigdy sesja sama sobie.

| Etykieta | Nadpisuje |
|---|---|
| `model:opus` | model → Opus |
| `effort:high` | effort → high |

### Cykl

| Etykieta | Znaczenie |
|---|---|
| `loop:iteration <n>` | Numer cyklu orchestratora (`docs/journal/cykl-NNNN.md`), w którym powstało issue. Każde issue pętli ją niesie; następca dziedziczy ją po rodzicu, a issue założone przez dozorcę dostaje ostatni numer + 1. Jest **bramką pola widzenia** pętli (patrz „Pole widzenia pętli”); rolę nadal wybiera `rola:*`. Człowiek, który chce puścić własne issue przez `ready`, dodaje obie: `rola:*` i `loop:iteration N`. |
| `loop:map` | Issue złączeniowe cyklu jako mapa cyklu: sub-issues to zadania cyklu, body to indeks decyzji. Informacyjna — pętla jej nie czyta; pole widzenia i rolę nadal dają `loop:iteration N` i `rola:*`. |

### Stan

| Etykieta | Znaczenie |
|---|---|
| `conflict` | Merge nieudany. Issue zostaje **otwarte** i odpala się ponownie ze świeżego HEAD. Konflikt nie jest porażką zadania. |

---

## Pole widzenia pętli

**Pętla widzi i dotyka wyłącznie issues z etykietą `loop:iteration N` (oraz z jedną `rola:*`, która mówi, kogo uruchomić).** Sama `rola:*` ani sama `ready` nie wystarcza. Właściciel
może w tym samym repo prowadzić własne issues i branche (np. wayfinderowe) — pętla ich nie ruszy
. Gwarantują to cztery miejsca, pilnowane testami w `tests/test_loop.py`:

| Miejsce | Zachowanie |
|---|---|
| `loop_open()` | Jedyne źródło dla dozorcy (`kick()`) i `commitments()`: `state=open` **i** etykieta `loop:iteration N` **i** `rola:*` |
| `dispatch.yml` | Tylko `workflow_dispatch` albo `issues: labeled` z etykietą dokładnie `ready` |
| `resolve()` | Odrzuca issue bez `loop:iteration N` albo bez dokładnie jednej etykiety `rola:*` |
| orchestrator | Pole widzenia = issues z `loop:iteration N`; nic spoza nich nie wchodzi do kontekstu |

**Gałęzie:** `merge_main()` pcha wyłącznie na gałąź domyślną i na własne `task/<n>`; cudzej gałęzi nie tyka.

**Ryzyko brzegowe — ręczna praca na `main`.** Jeśli właściciel pushuje na `main` w chwili epilogu,
`merge_main()` dostaje odrzucony push i ponawia rebase (do 5 razy, potem `conflict`). Issues
to nie dotyka — najwyżej zadanie wróci do kolejki ze świeżego HEAD. Kto chce mieć spokój,
pracuje na własnej gałęzi, nie na `main`.

---

## Uprawnienia

Domyślne uprawnienia workflow w repo są już na minimum i mają takie zostać:

| Ustawienie | Wartość |
|---|---|
| `default_workflow_permissions` | `read` |
| `can_approve_pull_request_reviews` | `false` |

Druga pozycja to w UI checkbox **„Allow GitHub Actions to create and approve pull
requests"**, siedzący tuż pod Workflow permissions. Nazwa mówi o zatwierdzaniu, ale
jedna opcja gasi **dwie** rzeczy: `GITHUB_TOKEN` nie może PR-a zatwierdzić **ani go
otworzyć**.

**Rozstrzygnięte: pętla nie otwiera PR-ów.** PR był tylko
powierzchnią audytu, bo epilog i tak merguje bezwarunkowo, a benchmark jest
nieblokujący. Epilog robi rebase `task/<n>` i pushuje na gałąź domyślną po zielonych
testach; audyt to `git log`. Checkbox zostaje wyłączony na stałe, `pull-requests: write`
i migracja na GitHub App znikają z planu.

Skoro domyślne to `read`, **każdy workflow musi jawnie zadeklarować `permissions:`**.
Minimalne zestawy:

| Workflow | `permissions:` |
|---|---|
| orchestrator | `actions: write`, `issues: write`, `contents: write` |
| sesja | `contents: write`, `issues: write`, `actions: write` |

`actions: write` jest tym, co pozwala pętli wywołać `workflow_dispatch` na samej sobie.

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

Oba potwierdzone przez właściciela 2026-09-20. Jeśli kiedyś przestaną się
zgadzać, nikt tego nie zauważy automatycznie — dlatego przegląd tych dwóch pozycji
należy do raportu tygodniowego, gdy ten powstanie.

Sekrety repo — w tym `CLAUDE_CODE_OAUTH_TOKEN` — i tak **nie są** przekazywane do
przebiegów z forkowych PR-ów.

---

## Gałąź pętli

**Gałąź pętli to gałąź domyślna repozytorium. Dziś `main`.** Nie są to dwa
pojęcia, które trzeba trzymać w zgodzie — to jedno pojęcie. Wymuszają to dwa
udokumentowane ograniczenia GitHuba, z których żadne nie ma obejścia:

| Ograniczenie | Skutek |
|---|---|
| *„Workflow runs cannot restore caches created for child branches or sibling branches"* — run czyta cache z własnej gałęzi **albo z domyślnej** | Stan emulatora, który wg ustaleń jedzie przez `actions/cache`, nie przechodzi między gałęziami siostrzanymi |
| Workflow na zdarzeniu `issues` odpala się **wyłącznie z pliku na gałęzi domyślnej**; `workflow_dispatch` jest na tej samej liście widoczny dopiero stamtąd | Ludzka ścieżka wejścia `issues: [labeled]` nie działa, dopóki workflowy leżą poza gałęzią domyślną |

### Nazwa nie jest wpisywana na sztywno

Workflow ustala gałąź pętli przez `github.event.repository.default_branch`,
nigdy przez literał `main`.

Powód jest jeden i wystarczający: **pętla nie może edytować `.github/workflows/`**
(akcja twardo tego zabrania). Nazwa wpisana na sztywno byłaby jedyną rzeczą, której
pętla nie umie naprawić, umieszczoną w jedynym miejscu, którego nie umie tknąć.
Przy odczycie z API zmiana nazwy gałęzi pętli to przestawienie gałęzi domyślnej
w ustawieniach repo — bez dotykania jednego pliku workflow.

### Stan emulatora: dwie warstwy cache'u

Sesja pracuje na `task/<n>`, więc **zapisuje** cache wyłącznie w zasięgu własnej
gałęzi — ale **czyta** także z gałęzi domyślnej. Stąd podział:

| Warstwa | Zasięg | Co niesie | Żywotność |
|---|---|---|---|
| Baza | gałąź domyślna | obraz systemu AVD + zainstalowany APK | między sesjami |
| Partia | `task/<n>` | `userdata-qemu.img.qcow2` bieżącej partii | między ogniwami **jednej** sesji |

Świeża sesja weryfikacyjna zaczyna partię od zera i to jest w porządku:
każda partia serii weryfikacyjnej (`CONTEXT.md`) mieści się w jednym jobie; ciągłość między sesjami nie jest
potrzebna.

**Merge na gałąź pętli w trakcie sesji weryfikacyjnej nie unieważnia jej cache'u.**
Wpis cache'u jest związany z kluczem i gałęzią, nie z commitem, a sesja siedzi na
własnym `task/<n>`, którego merge na gałąź domyślną nie dotyka. Pytanie o to zamknięte przecząco.

Klucze muszą być nowe przy każdym zapisie (`avd-<warstwa>-${{ github.run_id }}`)
i odczytywane przez `restore-keys`, bo wpis o danym kluczu jest niemutowalny (§5.3 badania cache).

---

## Workflowy

Cała logika siedzi w `.github/loop/loop.py` (sztywny kod, zero agenta), wołanym z YAML-i
jednolinijkowcami. Kod pętli biegnie z checkoutu **gałęzi domyślnej** (`loop/`), agent
pracuje w osobnym checkoutcie zadania (`work/`) — agent nie zmienia kodu, który go pilnuje.

| Plik | Wyzwalacz | Robi |
|---|---|---|
| `dispatch.yml` | `workflow_dispatch(issue)`; `issues: labeled` = `ready` | Jedyne publiczne wejście: dozór, walidacja, deduplikacja, start `session.yml`. |
| `session.yml` | `workflow_dispatch(issue)` | `prep` (dozór, sonda, rola → profil, model, budżet) → jeden z trzech kształtów: `plain`, `emulator`, `bench`. Każdy kończy krokiem **Epilog** (`if: always()`). |
| `watchdog.yml` | cron co 30 min | Bramka `awaria`, sonda, cztery liczniki, kopnięcia. Czerwony przebieg = mail. |

Odblokowanie dependentów robi sam epilog (w procesie, po zamknięciu issue) — osobny `unblock.yml` odpadł, bo epilog ma te same uprawnienia i to samo wywołanie.

### Wejście i wyjście agenta

Agent nie ma `gh`. Workflow zapisuje `.session/issue.md` (treść + komentarze zaufanych
autorów) i publikuje `.session/report.md` jako jeden komentarz z markerem (co 2 min
i w epilogu), razem z pushem `task/<n>`. Pola raportu `proby`, `wznow_po`, `kopniecia`,
`kopniete`, `konflikty`, `przyczyna`, `weryfikacja` należą do epilogu i dozorcy; publikacja
raportu agenta ich nie kasuje.

### Epilog

Jeden parametr: numer issue. Kolejność: publikacja raportu → przyczyna maszynowa
(`api_error_status`, `terminal_reason`, kod wyjścia — dosłownie, nigdy z `subtype`)
→ brak statusu terminalnego = `paused` przy limicie, inaczej `crashed` → `## Weryfikacja`
przy `done` (błąd = `partial`) → push `task/<n>` → **przy `done` rebase + testy + push na
gałąź domyślną** (konflikt: etykieta `conflict`, issue otwarte, ponowny start, max 3;
dotknięcie `.github/`, `.claude/skills/orchestrator/` albo `bench/record.json` bez roli
`bench` = `blocked`, bez scalenia) → zamknięcie + `report:unread`, następca z `## Następca`
(limit pokolenia 3, dziedziczy blokady rodzica), odblokowanie dependentów.

Nie-`done` **nie scala się** — gałąź `task/<n>` zostaje, a następca startuje z niej.
Merge'e szereguje git (odrzucony push = rebase i ponowienie), nie `concurrency: loop-merge`.

`paused`: etykieta `blocked:rate-limit`, `wznow_po` z terminu resetu w pliku wykonania,
a gdy go nie ma — backoff 1 h / 5 h / 24 h. Wznawia dozorca; więcej niż 3 próby albo
30 dni = `crashed`.

### Dozorca

Kolejność: dozór (`AUTOPILOT`, `GOAL_REACHED`) → **bramka `awaria`** (otwarta = cisza)
→ sonda poświadczenia (martwe = otwarcie `awaria` + `exit 1`) → sonda `ASSETS_READ_TOKEN`
(martwe = sam czerwony przebieg, bez `awaria`) → licznik `crashed` bez commita (3) →
wznowienie zaparkowanych → zobowiązania → kopnięcie (3 bezskuteczne = `awaria`).
Zero otwartych issues to zator: dozorca zakłada issue `rola:orchestrator` ze sztywnego szablonu.

### Licznik strat na okno

Piąty licznik, ale **nie dozorcy, tylko orchestratora**: most stanął na nieznanym
oknie, a jego `NNN_end.png` czeka w artefakcie. Klucz = `okno:` z raportu verifiera. Bez nowego
magazynu — licznik to pole `strata_okna: N` w `## Cel` kolejnych issues naprawczych tego
okna. **2** straty z rzędu = koniec łatania: jednorazowy pomiar klawisza „wstecz"
(`rola:verifier`), a gdy zawiedzie, etykieta `awaria`. Dozorca go nie liczy — dla niego
to zwykły przebieg z zaległym zadaniem.

### Sonda poświadczenia

```bash
curl -s -o /dev/null -w '%{http_code}' https://api.anthropic.com/v1/models   -H "Authorization: Bearer $CLAUDE_CODE_OAUTH_TOKEN"   -H "anthropic-version: 2023-06-01" -H "anthropic-beta: oauth-2025-04-20"
# 200 żyje · 401 martwy · 403 odwołany
```

Zaimplementowana w `loop.py probe`; brak odpowiedzi sieci to nie martwe poświadczenie.
Wygaśnięcie `CLAUDE_CODE_OAUTH_TOKEN` (rok od `claude setup-token`) i `ASSETS_READ_TOKEN`
(ok. 2026-10-21) to notatka dla właściciela — pętla dat nie czyta.

### Znane luki

- **Granica `.github/` stoi na drodze scalania, nie na pushu.** Agent z `Bash(git:*)` mógłby
  wypchnąć na gałąź domyślną wprost. Uszczelnienie wymaga reguły ochrony gałęzi (ustawienie
  właściciela) i świadomie nie jest tu zrobione.
- **Cache emulatora nie jest podpięty.** Zimny start z pobraniem obrazu; do decyzji po biegu na sucho.
- **`rola:bench` uruchamia polecenia z `## Weryfikacja`**, bez polityki rekordu i wag.
