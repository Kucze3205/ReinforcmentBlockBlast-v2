# Samowyzwalanie workflow: co jest potrzebne, żeby pętla się nie zatrzymała

Data badania: 2026-09-20. Wszystkie cytaty pochodzą z oficjalnej dokumentacji GitHuba (`docs.github.com`, źródła w `github/docs`) oraz z repozytoriów akcji należących do GitHuba.

Legenda wiarygodności użyta w całym dokumencie:

- **[POTWIERDZONE]** — dosłownie w dokumentacji, z linkiem.
- **[WNIOSEK]** — wynika logicznie z potwierdzonych faktów, ale nie jest wprost napisane.
- **[ZGADYWANE]** — moja ocena projektowa, do zweryfikowania empirycznie.

---

## 1. Dokładna reguła

**[POTWIERDZONE]** Oficjalne sformułowanie, dosłownie (`data/reusables/actions/actions-do-not-trigger-workflows.md`, wstawiane m.in. do [Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow) i [GITHUB_TOKEN](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)):

> When you use the repository's `GITHUB_TOKEN` to perform tasks, events triggered by the `GITHUB_TOKEN` will not create a new workflow run, with the following exceptions:
>
> - `workflow_dispatch` and `repository_dispatch` events always create workflow runs.
> - `pull_request` events with the `opened`, `synchronize`, or `reopened` activity types: when a workflow using `GITHUB_TOKEN` creates or updates a pull request, the resulting `pull_request` event creates workflow runs in an **approval-required** state. The pull request displays a banner in the merge box, and a user with write access to the repository can start the runs by selecting **Approve workflows to run**. Other `pull_request` activity types (such as `labeled`, `edited`, or `closed`) do not create workflow runs. This prevents recursive workflow runs while still allowing CI workflows to run on pull requests created by automation.
>
> For all other events, this behavior prevents you from accidentally creating recursive workflow runs. For example, if a workflow run pushes code using the repository's `GITHUB_TOKEN`, a new workflow will not run even when the repository contains a workflow configured to run when `push` events occur.

Konsekwencje wprost dla naszej pętli:

- **[POTWIERDZONE]** `issues` (w tym `opened` i `labeled`) **nie jest** na liście wyjątków. Issue utworzone przez `GITHUB_TOKEN` **nie odpali** workflow z `on: issues`. To dokładnie łamie projekt z mapy „utworzenie issue z etykietą roli odpala sesję", jeśli issue tworzy bot z `GITHUB_TOKEN`.
- **[POTWIERDZONE]** Dodatkowo: commity wypchnięte przez workflow z `GITHUB_TOKEN` nie wyzwalają builda GitHub Pages (`data/reusables/actions/actions-do-not-trigger-pages-rebuilds.md`).
- **[POTWIERDZONE]** Oficjalna droga obejścia, cytat z [Triggering a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow):
  > If you do want to trigger a workflow from within a workflow run, you can use a GitHub App installation access token or a personal access token instead of `GITHUB_TOKEN` to trigger events that require a token.

  I ostrzeżenie w tym samym akapicie:
  > To minimize your GitHub Actions usage costs, ensure that you don't create recursive or unintended workflow runs.

- **[POTWIERDZONE]** Reguła dotyczy **tokenu**, nie repozytorium. Issue utworzone ręcznie przez człowieka albo przez PAT/App zawsze wyzwala workflow normalnie. Czyli ścieżka „właściciel otwiera issue z etykietą → rusza sesja" działa bez żadnego dodatkowego poświadczenia.

---

## 2. Opcje obejścia — porównanie

| Opcja | Działa dla `issues: opened`? | Minimalne uprawnienia | Poświadczenie do ręcznego wygenerowania | Główne ryzyko |
|---|---|---|---|---|
| A. `GITHUB_TOKEN` + `workflow_dispatch` | Nie dotyczy — omija `issues` całkowicie | `permissions: actions: write` w pliku workflow | **żadne** | Trigger musi być jawnie wywołany; workflow musi istnieć na gałęzi domyślnej |
| B. `GITHUB_TOKEN` + `repository_dispatch` | Nie dotyczy — jw. | `permissions: contents: write` | **żadne** | `contents: write` to szerokie uprawnienie; run zawsze na gałęzi domyślnej |
| C. PAT fine-grained | **Tak** | Repozytoryjne: `Issues: write`, + zależnie od potrzeb `Contents: write`, `Actions: write`, `Pull requests: write`, `Variables: write`, obowiązkowo `Metadata: read` | tak — token w sekrecie | Wiązany z kontem człowieka; wygasa; limit 50 tokenów na konto; commity botów wyglądają jak commity właściciela |
| D. PAT klasyczny | **Tak** | scope `repo` (jedyny, jaki dokumentacja wymienia dla dispatchy) | tak — token w sekrecie | `repo` daje pełny dostęp do **wszystkich** repozytoriów użytkownika, także prywatnych. Nadmiarowe |
| E. GitHub App + installation token | **Tak** | Uprawnienia App: `Issues: Read & write`, `Contents: Read & write`, `Actions: Read & write`, `Pull requests: Read & write`, `Metadata: Read-only` | tak — App ID/Client ID + klucz prywatny w sekrecie | Najwięcej kroków konfiguracyjnych; klucz prywatny do rotacji |

### A. `workflow_dispatch` wywołany z `GITHUB_TOKEN`

- **[POTWIERDZONE]** Endpoint: `POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches`. Parametry: `ref` (wymagany, branch albo tag), `inputs` (opcjonalny, „The maximum number of properties is 25"). Źródło: [REST — Create a workflow dispatch event](https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event).
- **[POTWIERDZONE]** Uprawnienie fine-grained: **„Actions" repository permissions (write)**. Źródło: [Permissions required for fine-grained PATs](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2022-11-28). Ten sam zestaw nazw obowiązuje dla `GITHUB_TOKEN`, deklarowany kluczem `permissions: actions: write`.
- **[POTWIERDZONE]** Ograniczenie gałęzi: „This trigger only receives events when the workflow file is on the default branch." (`data/reusables/actions/workflow-dispatch.md`). Plik workflow musi być na `main`; sam run można dispatchować na dowolny `ref`, ale dopiero po tym, jak workflow raz się wykonał.
- **[POTWIERDZONE]** `GITHUB_SHA`/`GITHUB_REF` = ostatni commit na dispatchowanej gałęzi/tagu.
- **[POTWIERDZONE]** Zdarzenie `workflow_dispatch` **zawsze** tworzy run, także gdy wywołane `GITHUB_TOKEN`-em.

### B. `repository_dispatch` wywołany z `GITHUB_TOKEN`

- **[POTWIERDZONE]** Endpoint: `POST /repos/{owner}/{repo}/dispatches`. `event_type` (≤100 znaków), `client_payload` — **maksymalnie 10 właściwości najwyższego poziomu**, payload maks. **65 535 znaków**. Źródła: [events-that-trigger-workflows § repository_dispatch](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#repository_dispatch), [REST — Create a repository dispatch event](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#create-a-repository-dispatch-event).
- **[POTWIERDZONE]** Uprawnienie fine-grained: **„Contents" repository permissions (write)**. PAT klasyczny: scope `repo`.
- **[POTWIERDZONE]** Run zawsze startuje z gałęzi domyślnej: `GITHUB_SHA` = „Last commit on default branch", `GITHUB_REF` = „Default branch". Nie da się dispatchować na gałąź roboczą.
- **[WNIOSEK]** Względem opcji A jest gorsze dla nas: wymaga szerszego uprawnienia (`contents: write` zamiast `actions: write`), nie pozwala wybrać gałęzi, a jedno zdarzenie budzi **wszystkie** workflow nasłuchujące danego `event_type` — czyli fan-out jest rozproszony po plikach zamiast skupiony w orchestratorze.

### C. PAT fine-grained

- **[POTWIERDZONE]** Zalety wg [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens): token ograniczony do jednego właściciela zasobów, do wybranych repozytoriów, z granularnymi uprawnieniami; org może wymagać zatwierdzenia.
- **[POTWIERDZONE]** Wady i limity:
  - „Both fine-grained PATs and PATs (classic) are tied to the user who generated them and will become inactive if the user loses access to the resource."
  - „There is a limit of 50 fine-grained personal access tokens you can create."
  - Czas życia: „Infinite lifetimes are allowed but may be blocked by a maximum lifetime policy set by your organization or enterprise owner." — czyli dla repo osobistego można ustawić token bez wygaśnięcia, co jest wygodne dla pętli, ale zwiększa promień rażenia wycieku.
  - „Tokens always include read-only access to all public repositories on GitHub." — nie da się tego wyłączyć.
  - Dokumentacja wprost kieruje do App: „To access resources on behalf of an organization, or for long-lived integrations, you should use a GitHub App."
- **[POTWIERDZONE]** Dla `issues: opened` wystarczy repozytoryjne **`Issues: write`** (endpoint `POST /repos/{owner}/{repo}/issues`). Komentarz i edycja issue — to samo uprawnienie.
- **[WNIOSEK]** Wszystkie akcje pętli wyglądałyby jak akcje właściciela (autor issue, autor commitu). Dziennik pętli i audyt tracą rozróżnialność człowiek/bot, a to jest dokładnie ten sygnał, na którym opieramy strażnika przed rekurencją.

### D. PAT klasyczny

- **[POTWIERDZONE]** Dokumentacja REST dla obu endpointów dispatch mówi tylko: „OAuth app tokens and personal access tokens (classic) need the `repo` scope to use this endpoint." Nie ma węższego scope'u.
- **[POTWIERDZONE]** „If you choose to use a PAT (classic), keep in mind that it will grant access to all repositories within the organizations that you have access to, as well as all personal repositories in your personal account."
- **[WNIOSEK]** Dla repozytorium, które staje się publiczne i w którym autonomiczny agent wykonuje dowolny kod, `repo` jest nieakceptowalnie szerokie. Odrzucone.

### E. GitHub App + installation access token

- **[POTWIERDZONE]** Procedura z [Making authenticated API requests with a GitHub App in a GitHub Actions workflow](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow): zarejestruj App → Client ID jako zmienna konfiguracyjna → klucz prywatny jako sekret → zainstaluj App na koncie i nadaj dostęp do repo → w workflow wygeneruj token akcją `actions/create-github-app-token@v3`.
- **[POTWIERDZONE]** „An installation access token expires after 1 hour." ([README `actions/create-github-app-token`](https://github.com/actions/create-github-app-token#usage)). Krótkie życie to zaleta bezpieczeństwa i wada dla jobów dłuższych niż godzina.
- **[POTWIERDZONE]** Bot ma własną tożsamość. Akcja GitHuba udostępnia `steps.app-token.outputs.app-slug`, a README używa jej jako `"${{ steps.app-token.outputs.app-slug }}[bot]"` w `gh api /users/...` — czyli login aktora to `<app-slug>[bot]`. To daje twardy, sprawdzalny warunek na aktorze zdarzenia.
- **[POTWIERDZONE]** Limit API: instalacja App ma własny budżet 5 000 żądań/h (skalujący się z liczbą repo i użytkowników, maks. 12 500), niezależny od osobistego limitu 5 000/h właściciela. Źródło: [Actions limits § Commonly hit dependent service limits](https://docs.github.com/en/actions/reference/limits).
- **[POTWIERDZONE]** Nie jest wiązany z kontem człowieka — nie umiera, gdy właściciel traci dostęp.

---

## 3. Repo publiczne: limity, kolejkowanie, forki

Wszystko poniżej **[POTWIERDZONE]**, źródła: [Actions limits](https://docs.github.com/en/actions/reference/limits), [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions).

### Minuty i koszty

> GitHub Actions usage is **free** for **self-hosted runners** and for **public repositories** that use standard GitHub-hosted runners.

Założenie mapy („publiczne repo = nielimitowane minuty za darmo") jest potwierdzone — dla **standardowych** runnerów GitHub-hosted. Larger runners i GPU są płatne niezależnie od widoczności repo.

### Współbieżność — to jest realne wąskie gardło

| Runner | Plan | Łącznie jednoczesnych jobów | Maks. jednoczesnych jobów macOS |
|---|---|---|---|
| Standard GitHub-hosted | Free | **20** | 5 |
| Standard GitHub-hosted | Pro | 40 | 5 |
| Standard GitHub-hosted | Team | 60 | 5 |

Limit jest **per plan konta**, nie per repozytorium, i nie zależy od tego, czy repo jest publiczne. Support może go podnieść na zgłoszenie.

**[WNIOSEK]** Na darmowym planie pętla ma sufit 20 równoległych jobów. To jednocześnie naturalny hamulec (rozmnożenie sesji nie zamieni się w tysiąc runnerów) i twarde ograniczenie projektowe dla orchestratora: fan-out powyżej ~15 sesji naraz oznacza, że kolejne stoją w kolejce i zjadają limit czasu oczekiwania.

### Kolejkowanie i limity zdarzeń

| Limit | Wartość | Zachowanie po przekroczeniu |
|---|---|---|
| Workflow trigger event rate limit | 1 500 zdarzeń / 10 s / repozytorium | podnoszalny przez Support |
| Workflow run queued | 500 runów / 10 s | „the workflow runs that were supposed to be triggered by the webhook events will be blocked and will not be queued" — **niepodnoszalny** |
| Job execution time (GitHub-hosted) | 6 h | job zabity |
| Workflow run time | 35 dni | run anulowany |
| Re-run | 50 razy na run | podnoszalny |

**[WNIOSEK]** To są limity, o które zwykła pętla nie zahaczy, ale zbiegająca w nieskończoność rekurencja tak — i zachowaniem GitHuba nie jest wtedy „stop", tylko **ciche gubienie zdarzeń**. Czyli: limity platformy **nie są** naszym zabezpieczeniem. Zabezpieczenie musi być w workflow.

### Limity API

| Poświadczenie | Limit podstawowy |
|---|---|
| `GITHUB_TOKEN` w Actions | **1 000 żądań / h / repozytorium** |
| użytkownik (PAT) | 5 000 żądań / h, wspólny budżet dla wszystkich tokenów i aplikacji działających w jego imieniu |
| instalacja GitHub App | 5 000 żądań / h (skaluje się do maks. 12 500) |

Do tego niekonfigurowalne **secondary rate limits**.

**[WNIOSEK]** 1 000/h dla `GITHUB_TOKEN` jest współdzielone przez wszystkie równolegle biegnące joby w repo. Dwadzieścia sesji, z których każda intensywnie woła `gh api`, może to wyczerpać. To argument za tym, żeby sesje oszczędzały wywołania, i drugorzędny argument za App (osobny, większy budżet).

### Forki

- **[POTWIERDZONE]** „With the exception of `GITHUB_TOKEN`, secrets are not passed to the runner when a workflow is triggered from a forked repository." — czyli `CLAUDE_CODE_OAUTH_TOKEN` **nie wycieknie** przez PR z forka. To kluczowe dla repo publicznego.
- **[POTWIERDZONE]** „You can use the `permissions` key to add and remove `read` permissions for forked repositories, but typically you can't grant `write` access." — `GITHUB_TOKEN` w runie z forkowego PR jest read-only, chyba że admin włączył **Send write tokens to workflows from pull requests**. **Tej opcji nie wolno włączać.**
- **[POTWIERDZONE]** „Workflow runs triggered by a contributor's pull request from a fork may require manual approval from a maintainer with write access." Runy czekające na zatwierdzenie dłużej niż 30 dni są kasowane.
- **[POTWIERDZONE]** Uprawnienia repozytoryjne: **„Open issues"** ma każda rola, łącznie z Read — czyli na publicznym repo **dowolna osoba z internetu może otworzyć issue**. Ale **„Apply/dismiss labels"** mają dopiero role **Triage, Write, Maintain, Admin**.

**[WNIOSEK]** To jest najważniejszy pojedynczy wniosek dla bezpieczeństwa pętli na publicznym repo: **etykieta, nie samo istnienie issue, musi być spustem sesji**, bo obcy nie może nadać etykiety, a otworzyć issue może każdy. Wyzwalanie na `issues: opened` na publicznym repo oznacza, że każdy przechodzień może uruchomić płatną (choć darmową w minutach) sesję agenta, która wykonuje kod i zużywa limit Claude'a.

---

## 4. Mechanizmy hamujące rekurencję

### 4.1 `concurrency` — co naprawdę gwarantuje

**[POTWIERDZONE]** (`data/reusables/actions/actions-group-concurrency.md`, [Control workflow concurrency](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)):

> This means that there can be at most one running and one pending job in a concurrency group at any time. When a concurrent job or workflow is queued, if another job or workflow using the same concurrency group in the repository is in progress, the queued job or workflow will be `pending`. Any existing `pending` job or workflow in the same concurrency group, if it exists, will be canceled and the new queued job or workflow will take its place.

Ważne szczegóły:

- **[POTWIERDZONE]** Nazwa grupy jest **case-insensitive** (`prod` == `Prod`).
- **[POTWIERDZONE]** Kolejność FIFO wg czasu wejścia do kolejki, ale „ordering is not guaranteed".
- **[POTWIERDZONE]** `cancel-in-progress: true` ubija również run już biegnący.
- **[POTWIERDZONE]** Dozwolone konteksty w `group`: `github`, `inputs`, `vars`, `needs`, `strategy`, `matrix`.
- **[POTWIERDZONE]** W nowszym silniku (`queue: max`) do 100 runów może czekać w grupie; powyżej są odrzucane. Kombinacja `queue: max` + `cancel-in-progress: true` jest błędem walidacji.

**[WNIOSEK]** `concurrency` jest **dedupikatorem i serializatorem, nie licznikiem**. Ustawienie `group: orchestrator` gwarantuje, że nigdy nie biegnie więcej niż jeden orchestrator — to eliminuje klasę błędu „orchestrator wywołał sam siebie dwa razy i każda kopia rozmnożyła sesje". Ale **nie ogranicza łącznej liczby cykli w czasie**. Pętla o okresie 3 minut przy `group: orchestrator` biegnie w nieskończoność, po prostu szeregowo.

### 4.2 Warunek na aktorze zdarzenia

- **[POTWIERDZONE]** `github.actor` = „The username of the user that triggered the initial workflow run"; `github.triggering_actor` różni się przy re-runach.
- **[POTWIERDZONE]** Dla zdarzenia wywołanego przez App aktorem jest `<app-slug>[bot]`.

**[UWAGA — łatwa pomyłka]** Odruchowy strażnik `if: github.actor != 'moj-bot[bot]'` **zabije naszą pętlę**, bo to właśnie bot ma ją napędzać. Warunek na aktorze służy tu do czegoś odwrotnego: do **allowlisty** („tylko właściciel albo nasz bot mogą uzbroić sesję") i do rozróżnienia ścieżki ludzkiej od maszynowej. Odsiewanie po aktorze nie jest hamulcem rekurencji.

### 4.3 Etykieta jako strażnik jednorazowości

**[WNIOSEK + ZGADYWANE]** Wzorzec: sesja jako **pierwszy** krok zdejmuje etykietę-spust i zakłada `wayfinder:running`, używając `GITHUB_TOKEN`. Dwie własności:

1. Operacje na etykietach robione `GITHUB_TOKEN`-em **nie generują** kolejnych runów (`issues: labeled` nie jest wyjątkiem od reguły) — [POTWIERDZONE].
2. Powtórne nadanie etykiety przez człowieka to jedyny sposób na ponowne uruchomienie sesji na tym samym issue — intencjonalne, jawne [ZGADYWANE].

To jest tani, czytelny bezpiecznik idempotencji i zarazem bariera dla obcych (patrz § 3: etykiety wymagają roli Triage+).

### 4.4 Licznik pokoleń i budżet fan-outu

**[ZGADYWANE]** Limity platformy nie zatrzymają rekurencji (§ 3), więc trzeba własnego licznika:

- `depth` jako input `workflow_dispatch`, inkrementowany przy każdym dispatchu, twardy sufit (np. 200). Cykl, który przekracza sufit, nie dispatchuje następnego, tylko otwiera issue „pętla zatrzymana na limicie pokoleń".
- Sufit fan-outu na cykl (np. 8 sesji), z zapasem względem 20 jednoczesnych jobów planu Free.
- Bezpiecznik tempa: orchestrator liczy runy z ostatniej godziny (`gh api "/repos/$REPO/actions/runs?created=>$(date -u -d '1 hour ago' +%FT%TZ)" --jq .total_count`) i przy przekroczeniu progu zatrzymuje pętlę zamiast dispatchować.

### 4.5 Przełącznik `AUTOPILOT` — znalezione ograniczenie

**[POTWIERDZONE]** Klucz `permissions` w workflow zna dokładnie te zakresy: `actions`, `artifact-metadata`, `attestations`, `checks`, `code-quality`, `contents`, `deployments`, `id-token`, `issues`, `discussions`, `packages`, `pages`, `pull-requests`, `security-events`, `statuses`, `vulnerability-alerts` (`data/reusables/actions/github-token-available-permissions.md`). **Nie ma w tej liście `variables` ani `administration`.**

**[POTWIERDZONE]** Zapis zmiennej repo (`POST/PATCH /repos/{owner}/{repo}/actions/variables`) wymaga uprawnienia repozytoryjnego **„Variables" (write)**, a dla PAT klasycznego — scope `repo`.

**[WNIOSEK]** `GITHUB_TOKEN` **nie może** ustawić zmiennej repo `AUTOPILOT`. Czyli:

- `AUTOPILOT` jako **zmienna repo** działa doskonale jako przełącznik **dla człowieka** (mapa: „właściciel włącza przełącznik i nie wraca") — odczyt przez `vars.AUTOPILOT` jest darmowy i nie wymaga niczego.
- Ale **pętla nie może sama się wyłączyć** przez tę zmienną. Samowyzwalający się bezpiecznik musi trzymać stan tam, gdzie `GITHUB_TOKEN` ma zapis: **plik w repo** na gałęzi domyślnej (`contents: write`) albo **przypięty issue** pełniący rolę rygla (`issues: write`).

To jest korekta założenia mapy, nie jego unieważnienie — patrz § 8.

---

## 5. REKOMENDACJA

> **Nie generować żadnego nowego poświadczenia. Napędzać pętlę `GITHUB_TOKEN`-em przez `workflow_dispatch`, zachowując `issues: labeled` jako ścieżkę ludzką.**

Czyli workflow sesji ma **dwa** wyzwalacze:

```yaml
on:
  issues:
    types: [labeled]        # ścieżka ludzka — działa, bo człowiek to nie GITHUB_TOKEN
  workflow_dispatch:         # ścieżka pętli — jawny wyjątek od ochrony przed rekurencją
```

### Uzasadnienie

1. **[POTWIERDZONE]** `workflow_dispatch` zawsze tworzy run, także wywołany `GITHUB_TOKEN`-em. Problem z biletu znika **bez żadnego poświadczenia**.
2. **Usunięcie zamiast obejścia.** Wszystkie pozostałe opcje dokładają byt do utrzymania: rejestrację App + klucz prywatny + rotację, albo PAT wiązany z kontem człowieka, wygasający i z limitem 50 sztuk. Opcja A nie dokłada nic — uprawnienie deklaruje się jedną linijką `permissions: actions: write` w pliku, który i tak istnieje.
3. **Fan-out staje się jawny i skupiony w jednym miejscu.** Przy `issues: opened` jako spuście każde utworzone issue *implicite* rodzi sesję, a liczba sesji jest funkcją tego, ile issues orchestrator przypadkiem wygenerował. Przy `workflow_dispatch` orchestrator musi **wymienić z nazwy** każdą sesję, którą uruchamia. Ten sam plik, który tworzy issues, decyduje o uruchomieniach — więc licznik pokoleń i sufit fan-outu da się egzekwować w jednym miejscu, a nie rozsmarować po `if`-ach w pięciu workflow. To jest **strukturalny** hamulec rekurencji, nie policyjny.
4. **Najmniejszy promień rażenia.** `actions: write` ograniczone do jednego repo i do czasu życia joba, kontra `repo` (wszystko, co ma właściciel) albo długowieczny PAT w sekrecie repozytorium publicznego, w którym agent wykonuje dowolny kod.
5. **Jedyna realna strata jest do zaakceptowania.** Tracimy „bot tworzy issue → issue samo odpala sesję". Mapa i tak zakłada, że to orchestrator decyduje o kolejności i blokadach — więc jawne uruchomienie jest bliższe intencji niż kaskada zdarzeniowa.

### Kiedy ta rekomendacja przestaje wystarczać

**[POTWIERDZONE]** Jeden warunek wymusza przejście na **opcję E (GitHub App)**: gdy pętla zacznie otwierać pull requesty i oczekiwać, że CI na nich ruszy **bez kliknięcia człowieka**. PR-y tworzone `GITHUB_TOKEN`-em dają runy w stanie **approval-required**. Dopóki benchmark liczy się wewnątrz joba sesji (a mapa mówi, że benchmark jest nieblokujący i raportowany przez sesję), problemu nie ma.

Drugi, słabszy warunek [WNIOSEK]: gdy pętla ma sama wyłączać `AUTOPILOT` jako zmienną repo — to wymaga `Variables: write`, czyli PAT-a albo App. Tańsze wyjście to trzymanie rygla awaryjnego w pliku repo (§ 4.5).

**Gdy przyjdzie czas na App, a nie PAT** — bo App nie umiera z kontem człowieka, ma własny budżet API, token żyje godzinę, a zdarzenia mają rozróżnialnego aktora `<app-slug>[bot]`, na którym można oprzeć audyt i dziennik pętli.

---

## 6. Dokładna lista uprawnień do nadania

### Dla rekomendacji (opcja A) — nic do wyklikania

Wszystko deklaratywne w plikach workflow. **[POTWIERDZONE]** — każde z tych uprawnień istnieje w kluczu `permissions`:

| Workflow | Uprawnienie | Po co |
|---|---|---|
| orchestrator | `actions: write` | `POST .../workflows/{id}/dispatches` — uruchomienie sesji |
| orchestrator | `issues: write` | tworzenie issues z zadaniami, komentarze, zamykanie |
| orchestrator | `contents: write` | zapis dziennika pętli i pliku rygla awaryjnego |
| sesja | `contents: write` | commit i push efektów pracy |
| sesja | `issues: write` | raport w komentarzu, zdjęcie/nadanie etykiet, zamknięcie |
| sesja | `actions: write` | oddanie sterowania — dispatch orchestratora |
| sesja | `pull-requests: write` | **tylko jeśli** sesja otwiera PR-y |

Zasada z dokumentacji, o której trzeba pamiętać — **[POTWIERDZONE]**: „If you specify the access for any of these permissions, all of those that are not specified are set to `none`." Czyli jawna lista automatycznie odcina resztę.

Ustawienia repozytorium do sprawdzenia ręcznie:
- Settings → Actions → General → Workflow permissions: musi być **Read and write permissions** albo klucz `permissions` w każdym pliku (rekomendowane to drugie, i zostawienie domyślnej wartości restrykcyjnej).
- Settings → Actions → General: **„Send write tokens to workflows from pull requests" — MUSI pozostać wyłączone.** [POTWIERDZONE, § 3]
- Settings → Actions → General: „Require approval for all external contributors" dla runów z forków.
- Zmienna repo `AUTOPILOT` (Settings → Secrets and variables → Actions → Variables) — tylko do odczytu przez pętlę.
- Sekret `CLAUDE_CODE_OAUTH_TOKEN` — **jedyne poświadczenie, które właściciel musi wygenerować ręcznie.**

### Gdyby jednak opcja E (GitHub App) — uprawnienia App

**[POTWIERDZONE]** nazwy uprawnień, mapowanie na endpointy z dokumentacji fine-grained:

| Uprawnienie App | Poziom | Po co |
|---|---|---|
| Metadata | Read-only | obowiązkowe, wymuszane automatycznie |
| Issues | Read & write | `POST /repos/.../issues`, komentarze, etykiety, zamykanie |
| Contents | Read & write | push, `repository_dispatch` |
| Actions | Read & write | `workflow_dispatch`, odczyt listy runów dla bezpiecznika tempa |
| Pull requests | Read & write | tylko jeśli pętla otwiera PR-y |
| Variables | Read & write | tylko jeśli pętla ma sama przestawiać `AUTOPILOT` |

Plus, w repo: zmienna `APP_CLIENT_ID` i sekret `APP_PRIVATE_KEY`.

### Gdyby opcja C (PAT fine-grained) — uprawnienia tokenu

**[POTWIERDZONE]** Resource owner: `Kucze3205`. Repository access: **Only select repositories → to repo**. Permissions: `Metadata: Read-only` (wymuszone), `Issues: Read and write`, `Contents: Read and write`, `Actions: Read and write`, opcjonalnie `Pull requests: Read and write`, `Variables: Read and write`.

---

## 7. Gotowe fragmenty YAML

Wszystko poniżej to **[ZGADYWANE]** w sensie konkretnych progów i nazw; składnia i użyte konteksty są **[POTWIERDZONE]**.

### 7.1 Sesja — dwa wyzwalacze, strażnik autopilota, rygiel etykietowy

```yaml
name: session

on:
  issues:
    types: [labeled]          # ścieżka ludzka
  workflow_dispatch:           # ścieżka pętli
    inputs:
      issue:
        description: 'Numer issue do zrealizowania'
        required: true
        type: string
      depth:
        description: 'Numer pokolenia pętli'
        required: true
        type: string

permissions:
  contents: write
  issues: write
  actions: write

# Rygiel idempotencji: to samo issue nigdy nie biegnie dwa razy naraz,
# a drugi dispatch czeka zamiast kasować pierwszy.
concurrency:
  group: session-${{ inputs.issue || github.event.issue.number }}
  cancel-in-progress: false

jobs:
  run:
    # Trzy warunki naraz:
    #  1. autopilot włączony (ubija też sesje uzbrojone tuż przed wyłączeniem),
    #  2. etykieta faktycznie jest rolą (ścieżka ludzka),
    #  3. sufit pokoleń nie przekroczony (ścieżka pętli).
    if: >-
      vars.AUTOPILOT == 'on' &&
      (github.event_name == 'workflow_dispatch' ||
       startsWith(github.event.label.name, 'wayfinder:')) &&
      fromJSON(inputs.depth || '0') < 200
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      # Rygiel awaryjny, który GITHUB_TOKEN POTRAFI przestawić
      # (w odróżnieniu od zmiennej repo AUTOPILOT — patrz sekcja 4.5).
      - name: Sprawdź rygiel awaryjny
        run: |
          if [ -f .github/loop-halt ]; then
            echo "::error::Rygiel awaryjny założony: $(cat .github/loop-halt)"
            exit 1
          fi

      # Zdjęcie etykiety-spustu GITHUB_TOKENEM nie wygeneruje kolejnego runu.
      - name: Uzbrój rygiel jednorazowości
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ISSUE: ${{ inputs.issue || github.event.issue.number }}
        run: |
          gh issue edit "$ISSUE" --add-label 'wayfinder:running'

      # ... właściwa sesja agenta ...
```

### 7.2 Orchestrator — singleton, sufit fan-outu, bezpiecznik tempa

```yaml
name: orchestrator

on:
  workflow_dispatch:
    inputs:
      depth:
        required: true
        type: string

permissions:
  contents: write
  issues: write
  actions: write

# Singleton: nigdy dwa orchestratory naraz. cancel-in-progress: false,
# bo skasowanie biegnącego cyklu zostawiłoby issues bez sesji.
concurrency:
  group: orchestrator
  cancel-in-progress: false

env:
  MAX_DEPTH: '200'
  MAX_FANOUT: '8'      # zapas względem 20 jednoczesnych jobów planu Free
  MAX_RUNS_PER_HOUR: '120'

jobs:
  plan:
    # Uwaga: kontekst `env` nie jest dostępny w `jobs.<id>.if`, więc sufit
    # pokoleń jest tu literałem, a nie odwołaniem do MAX_DEPTH.
    if: vars.AUTOPILOT == 'on' && fromJSON(inputs.depth) < 200
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6

      - name: Bezpiecznik tempa — zakładaj rygiel, nie dispatchuj
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          SINCE=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
          RUNS=$(gh api "/repos/${{ github.repository }}/actions/runs?created=>${SINCE}" --jq '.total_count')
          echo "Runów w ostatniej godzinie: $RUNS (próg $MAX_RUNS_PER_HOUR)"
          if [ "$RUNS" -gt "$MAX_RUNS_PER_HOUR" ]; then
            echo "tempo ${RUNS}/h przekroczyło próg ${MAX_RUNS_PER_HOUR} o $(date -u)" > .github/loop-halt
            git config user.name 'github-actions[bot]'
            git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
            git add .github/loop-halt && git commit -m 'chore: rygiel awaryjny pętli'
            git push
            gh issue create --title 'Pętla zatrzymana: bezpiecznik tempa' \
                            --body "Runów w ostatniej godzinie: ${RUNS}. Rygiel .github/loop-halt założony."
            exit 1
          fi

      - name: Dispatch sesji z sufitem fan-outu
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          NEXT_DEPTH: ${{ fromJSON(inputs.depth) + 1 }}
        run: |
          # ISSUES: lista numerów wyznaczona przez orchestratora, po jednym w linii.
          head -n "$MAX_FANOUT" issues.txt | while read -r N; do
            gh workflow run session.yml -f issue="$N" -f depth="$NEXT_DEPTH"
          done
```

### 7.3 Ostatnia sesja oddaje sterowanie

```yaml
      - name: Oddaj sterowanie orchestratorowi
        if: vars.AUTOPILOT == 'on' && hashFiles('.github/loop-halt') == ''
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh workflow run orchestrator.yml -f depth="${{ inputs.depth }}"
```

### 7.4 Anty-hamulec, którego NIE stosować

```yaml
# ŹLE — to zabije pętlę, bo to właśnie bot ma ją napędzać.
if: github.actor != 'github-actions[bot]'
```

Warunek na aktorze służy do **allowlisty**, nie do blokowania botów:

```yaml
# DOBRZE — obcy z publicznego repo nie uzbroi sesji.
# (i tak jest redundantne: etykiety wymagają roli Triage+, patrz sekcja 3)
if: >-
  github.event_name == 'workflow_dispatch' ||
  contains(fromJSON('["Kucze3205"]'), github.event.sender.login)
```

---

## 8. Co to robi z założeniami mapy

| Założenie mapy | Werdykt |
|---|---|
| „Publiczne repo ma nielimitowane minuty Actions" | **Potwierdzone** — dla standardowych runnerów GitHub-hosted. |
| „Wyzwalanie: utworzenie issue z etykietą roli odpala sesję" | **Wymaga korekty.** Działa dla issues tworzonych przez człowieka. Dla issues tworzonych przez pętlę `GITHUB_TOKEN`-em **nie zadziała w ogóle**. Rekomendacja: zostawić etykietę jako ścieżkę ludzką i dodać `workflow_dispatch` jako ścieżkę maszynową. |
| „Przełącznik autopilota: zmienna repo `AUTOPILOT`" | **Częściowo podważone.** Jako przełącznik dla człowieka — idealny. Jako bezpiecznik, który pętla przestawia sama — **niemożliwy**, bo `GITHUB_TOKEN` nie ma uprawnienia `Variables`. Potrzebny drugi rygiel w pliku repo albo w issue. |
| „Komputer właściciela nie bierze udziału w niczym" | **Potwierdzone i wzmocnione** przez rekomendację: zero poświadczeń do ręcznej rotacji poza `CLAUDE_CODE_OAUTH_TOKEN`. |
| Cisza mapy nt. współbieżności | **Nowe ograniczenie:** plan Free = **20 jednoczesnych jobów** na całe konto. Sufit fan-outu orchestratora musi to respektować. |
| Cisza mapy nt. drive-by z publicznego repo | **Nowe ryzyko:** każdy może otworzyć issue w publicznym repo; etykiety wymagają roli Triage+. Spustem musi być etykieta, nigdy `issues: opened`. |

---

## 9. Źródła

Wszystkie odwiedzone 2026-09-20.

1. [Triggering a workflow — Triggering a workflow from a workflow](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow#triggering-a-workflow-from-a-workflow)
2. [GITHUB_TOKEN — When GITHUB_TOKEN triggers workflow runs](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs)
3. Źródło reguły: [`data/reusables/actions/actions-do-not-trigger-workflows.md`](https://github.com/github/docs/blob/main/data/reusables/actions/actions-do-not-trigger-workflows.md)
4. [Events that trigger workflows — `workflow_dispatch`, `repository_dispatch`, `issues`](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)
5. [REST — Create a workflow dispatch event](https://docs.github.com/en/rest/actions/workflows?apiVersion=2022-11-28#create-a-workflow-dispatch-event)
6. [REST — Create a repository dispatch event](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#create-a-repository-dispatch-event)
7. [Permissions required for fine-grained personal access tokens](https://docs.github.com/en/rest/authentication/permissions-required-for-fine-grained-personal-access-tokens?apiVersion=2022-11-28)
8. [Managing your personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
9. [Making authenticated API requests with a GitHub App in a GitHub Actions workflow](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)
10. [`actions/create-github-app-token` README](https://github.com/actions/create-github-app-token#readme)
11. [Actions limits](https://docs.github.com/en/actions/reference/limits)
12. [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
13. [Control the concurrency of workflows and jobs](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency)
14. [Workflow syntax — `permissions`](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#permissions)
15. [Contexts — `github` context](https://docs.github.com/en/actions/reference/workflows-and-actions/contexts#github-context)
16. [Approving workflow runs from forks](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)
17. [Repository roles for an organization](https://docs.github.com/en/organizations/managing-user-access-to-your-organizations-repositories/managing-repository-roles/repository-roles-for-an-organization)
18. [REST — Actions variables](https://docs.github.com/en/rest/actions/variables?apiVersion=2022-11-28)

---

## 10. Benchmark

**Nie dotyczy** — bilet badawczy, brak zmian w kodzie agenta ani w symulatorze.
