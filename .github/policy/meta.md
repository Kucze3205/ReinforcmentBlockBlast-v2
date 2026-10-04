# Zadanie: popraw politykę drzewa

Poprawiasz jeden program: `policy.py` w tym katalogu. Edytuj tylko ten plik. Nie ma tu nic
innego do zrobienia i nie masz innych narzędzi niż czytanie i edycja plików.

## Czym jest polityka

Drzewo to zapis prób: węzeł to jedna próba poprawy kodu agenta w grze, z wynikiem `s_v`
(większy lepszy) i czasem w godzinach. Próby tworzą łańcuchy: łańcuch zaczyna się od korzenia,
a każdy następny węzeł `c.d` poprawia poprzedni `c.(d-1)`. Polityka decyduje, jakie próby
otworzyć w następnej rundzie, a każda runda to paczka najwyżej `W` węzłów naraz:

- `None` otwiera nowy łańcuch od korzenia,
- nazwa czubka łańcucha (np. `"2.3"`) kontynuuje ten łańcuch,
- pusta lista kończy drzewo.

Drzewo kończy się też po `K` rundach.

## Cel

Wartość polityki na jednym drzewie to `V = max s_v − beta · T`. `T` to czas ścienny w godzinach:
runda kosztuje czas najdłuższego węzła w paczce, `T` to suma po rundach. Polityka ma więc znaleźć
wysoki `s_v` małym kosztem: nie otwierać prób, które nie rokują, ale otwierać naraz niezależne
próby, które rokują, bo paczka kosztuje tyle co jej najdłuższy węzeł. Wartość polityki to średnia
`V` po wszystkich zamkniętych drzewach w `drzewa/`. `W`, `K` i `beta` są w `konfiguracja.json`.

Wartość liczy osobny program, nie ty. Odtwarza twoją politykę na każdym zapisanym drzewie:
`solve` dostaje te same obserwacje co na żywo, a zamiast uruchamiać próbę ujawnia zapisany węzeł.
Nowy łańcuch dostaje najwcześniej utworzony jeszcze nieużyty korzeń zapisanego drzewa. Jeśli
zapisu następnej próby łańcucha nie ma, łańcuch się kończy (znika z `legal_actions()`), bez
kary w `T`. Runda, w której nic się nie ujawniło, nie liczy się do `K`.

## Interfejs

`solve(question)` zwraca listę akcji. Musi być deterministyczna: bez losowania, czasu, plików
i niczego poza `question`. Odtworzenie liczone jest dwa razy i musi dać ten sam wynik. Tylko
biblioteka standardowa.

`question`:

- `max_parallelism` (W), `max_rounds` (K), `round` (ukończone rundy), `baseline_score`,
- `observed()`: lista ocenionych dotąd węzłów, każdy to słownik z `wezel`, `lancuch`,
  `glebokosc`, `rodzic`, `s_v` i `delta` (`s_v` minus `s_v` rodzica; dla korzenia minus baseline),
  w kolejności łańcuch, głębokość,
- `legal_actions()`: `None` i czubki łańcuchów, które mają jeszcze ciąg.

Maszyneria odrzuca akcje spoza `legal_actions()`, powtórzenia czubka i to, co ponad `W`. Widzisz
tylko to, co dotąd ujawnione. Nie znasz wyniku prób, których jeszcze nie otwarto.

## Co masz na dysku

- `policy.py`: najlepsza dotąd wersja. To od niej zaczynasz.
- `history/`: wcześniejsze wersje. `history/biezaca/r0000/` to polityka sprzed tej fazy.
  W każdej wersji: `policy.py`, `wynik.json` (`V`, `V_drzewa`, `T_h_drzewa`, `blad` jeśli
  odtworzenie się nie udało) i `slady/<drzewo>.txt` (co polityka robiła w każdej rundzie
  odtworzenia i jak się skończyło). Katalogi `history/faza-*/` to wersje z wcześniejszych faz,
  bez śladów; ich `V` liczono na mniejszej liczbie drzew, więc nie porównuj ich bezpośrednio.
- `drzewa/<t>/manifest.json`: zapisane drzewa: węzły z `rodzic`, `kolejnosc` utworzenia,
  `s_v` i `koszt_h`, rundy (`paczki`) i zamknięcie. Bez kodu i bez notatek.
- `baseline.json`, `konfiguracja.json`.

Zacznij od `wynik.json` i śladów wersji z najniższym i najwyższym `V`: sprawdź, *dlaczego*
ta wersja wygrała albo przegrała na konkretnych drzewach, zamiast zgadywać.

## Zasady

- Zaufaj `V` z `wynik.json`, nie temu, co wersja twierdzi o sobie w komentarzu.
- Nie zbieraj się w lokalnym optimum. Jeśli kolejne wersje różnią się o drobiazg bez zysku,
  zmień strukturę decyzji, nie próg.
- Każda decyzja (zamknij łańcuch, rozszerz, zrównoleglij, zatrzymaj) musi wynikać z `observed()`.
  Nie używaj numerów konkretnych węzłów, wyników z `manifest.json` ani niczego, co wiesz o
  zapisanych drzewach: przyszłe drzewa będą inne, a polityka ma z nich skorzystać, nie z tych.
- Płytki słaby wynik nie wystarcza, żeby porzucić łańcuch: głębsze próby mogą go odbić. Spadek
  jednego węzła po dobrym nie wymazuje dobrego węzła.
- Polityka musi się zawsze skończyć: pusta lista, gdy nie ma czego otwierać.
- Błąd w pliku (wyjątek, brak `solve`, nie-lista, nie-deterministyczność, ponad 10 minut)
  unieważnia wersję. Przejrzyj kod, zanim skończysz.

Kiedy skończysz, zostaw w `policy.py` jedną zmienioną wersję i napisz w jednym zdaniu, co
zmieniłeś i dlaczego. Jeśli nie widzisz zmiany, która by pomogła, zostaw plik bez zmian.
