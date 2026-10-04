# Block Blast — autonomiczna pętla agentowa

Repozytorium niesie dwie rzeczy naraz: reimplementację gry Block Blast wraz z
agentem, który się w nią gra, oraz pętlę agentową, która ten kod rozwija bez
udziału człowieka. Glosariusz opisuje pętlę — jej terminy łatwo pomylić z
terminami gry.

## Język

### Pętla i jej gałęzie

**Pętla**:
Samopodtrzymujący się cykl sesji agentowych w GitHub Actions, rozwijający
agenta aż do osiągnięcia celu z mapy. Włączana i wyłączana wyłącznie przez
człowieka, zmienną repo `AUTOPILOT`.

**Gałąź pętli**:
Gałąź domyślna repozytorium — te dwa określenia znaczą dokładnie to samo i
nigdy nie mogą się rozejść. Dziś `main`.
_Avoid_: gałąź główna, mainline, trunk, `main` jako nazwa w kodzie workflow

**Gałąź zadania**:
`task/<n>`, gdzie `n` to numer issue. Gałąź jednej sesji, scalana w gałąź pętli
przez epilog. Nie widzi cache'u ani plików żadnej innej gałęzi zadania.
_Avoid_: gałąź robocza, feature branch

### Jednostki pracy

**Cykl**:
Odcinek pracy pętli od jednego issue `rola:orchestrator` do następnego: jedna
mapa zadań, sesje, które ją wykonują, i issue złączeniowe, które budzi kolejnego
orchestratora. Jednostka, w której liczy się postęp i w której powstaje jeden
wpis do dziennika.
_Avoid_: obrót, runda, iteracja pętli

**Sesja**:
Jedno uruchomienie agenta Claude Code, wyzwolone przez issue z etykietą
`rola:*`, kończące się raportem w komentarzu i zamknięciem issue.

**Ogniwo**:
Pojedynczy przebieg workflow w łańcuchu składającym się na jedną długą sesję.
Istnieje, bo job w Actions ginie po 6 h, a limit subskrypcji może uciąć pracę
wcześniej — dlatego każde ogniwo zapisuje stan przed końcem.
_Avoid_: etap, krok, iteracja

**Epilog**:
Krok workflow wykonywany zawsze, także po śmierci agenta. Dowozi raport, scala
gałąź zadania i wypycha odblokowanych dependentów. Nie jest agentem.

**Rola**:
Para skill + profil uprawnień, wybierana etykietą `rola:<nazwa>`. Zatrudnienie
nowej roli nie wymaga edycji workflow.
_Avoid_: tryb, persona, typ agenta

### Pamięć i okna

**Dziennik pętli**:
`docs/journal/cykl-NNNN.md`, jeden plik na cykl, pisany przez orchestratora.
Pamięć pętli: jedyne, co przeżywa koniec sesji, i jedyne wejście orchestratora
startującego na zimno. Indeks, nie magazyn — niesie sedno i link do raportu,
nigdy przepisaną treść.
_Avoid_: log, historia, notatki

**Stan**:
Ostatnia sekcja wpisu do dziennika, przepisywana i kompresowana z poprzedniego
cyklu. Czyni najnowszy plik samowystarczalnym, więc orchestrator nie czyta
historii. Jedyny fragment dziennika z limitem długości.

**Raport tygodniowy**:
`RAPORT.md` w korzeniu repo. Okno właściciela: proza, nadpisywana, historia w
`git log`. Nie myli się z raportem sesji, którym jest komentarz przy issue.
_Avoid_: raport (bez przymiotnika, gdy w pobliżu jest raport sesji)

**Awaria**:
Stan spoczynku pętli: orchestrator wyczerpał wszystkie próby i praca nie ruszy
bez ręki człowieka. Otwarte issue z etykietą `awaria` ucisza dozorcę, więc
pętla nie kopie w próżnię i nie pali limitu. Jedyny stan, w którym brak
przebiegów nie jest zatorem.
_Avoid_: błąd, awaria sesji, crash

**Dozorca**:
Sztywny skrypt na cronie, bez agenta, spoza łańcucha pętli. Wykrywa zator i
kopie, zanim zawoła. Milczy, dopóki `awaria` jest otwarta.
_Avoid_: watchdog, monitor, strażnik

### Cel i weryfikacja

**Cel**:
Agent nie przegrywa. 1 mln punktów licznika apki to limit długości partii
ustalony przez właściciela, nie miara poziomu: partia, która do niego dotrwa,
dowodzi nieprzegrywania. Punkty są rozstrzygnięciem remisu, nigdy kosztem
przeżycia.
_Avoid_: 1 mln jako wynik do pobicia, „nasz wzór" jako licznik celu

**Seria weryfikacyjna**:
10 partii na oryginale granych równolegle, każda na osobnym emulatorze. Zaliczona,
gdy każda z 10 dochodzi do 1 mln licznika apki bez przegranej. W danej chwili
trwa co najwyżej jedna seria.
_Avoid_: łańcuch weryfikacji, partia do celu (w liczbie pojedynczej)

**Przegrana**:
Koniec partii, bo żaden klocek z tacki nie mieści się na planszy — wina
algorytmu. Liczy się do serii i blokuje cel.
_Avoid_: śmierć (poza symulatorem), porażka, przerwanie

**Przerwanie**:
Koniec partii z winy infrastruktury: most stanął na nieznanym oknie, skończył
się czas joba, zginął runner. Nie wlicza się do serii; partię gra się od nowa.
_Avoid_: przegrana, awaria
