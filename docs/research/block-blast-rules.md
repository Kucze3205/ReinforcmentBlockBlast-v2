# Jak prawdziwy Block Blast punktuje i dobiera klocki

Data badania: 2026-09-20

Gra: **Block Blast!** (`com.block.juggle`), wydawca **Hungry Studio / ARETIS LIMITED**.

Dokument dzieli ustalenia na trzy rozłączne kategorie i **nie miesza ich**:

- **[F] FAKT POTWIERDZONY** — zweryfikowany w źródle pierwotnym, które *jest właścicielem*
  tej informacji (kod źródłowy, materiał wydawcy). Podane źródło i cytat/linia.
- **[P] POWTARZANA PLOTKA** — twierdzenie krążące po stronach-farmach SEO, poradnikach
  i wątkach graczy, bez ujawnionej metodyki pomiaru.
- **[D] WŁASNY DOMYSŁ** — moja interpretacja, hipoteza lub wniosek z zestawienia źródeł.

---

## 0. Streszczenie w trzech zdaniach

Wydawca **nie publikuje żadnych reguł punktacji ani doboru klocków** — sprawdzone
materiały oficjalne (blockblast.com, App Store, Google Play) opisują tylko planszę 8×8,
trzy oferowane klocki i brak rotacji. Dwie **niezależne reimplementacje z otwartym kodem**
zbiegają się na *identycznym* wzorze na czyszczenie linii — `combo_po_inkrementacji ×
10·ℓ·(ℓ−1)` (z `ℓ=1` traktowanym jako `10`) plus `+300` za pustą planszę — a obie modelują
combo jako **mnożnik**, który przeżywa kilka postawień bez czyszczenia, a nie jak nasz
addytywny bonus zerowany co turę. Doboru trzech klocków **nikt publicznie nie zmierzył**
na żywej apce; najlepsze dostępne implementacje albo zakładają losowanie jednostajne
(świadomie, jako uproszczenie), albo — w przypadku klonów przeglądarkowych — same
przyznają, że *ich własny* generator jest świadomy stanu planszy, i jednocześnie
zastrzegają, że o oficjalnej apce nic z tego nie wynika.

---

## 1. Materiały wydawcy — co Hungry Studio faktycznie mówi

### [F] Potwierdzone reguły podstawowe

| Reguła | Źródło |
|---|---|
| Plansza **8×8** | [App Store — opis dewelopera](https://apps.apple.com/us/app/block-blast/id1617391485) („8x8 board"), [Google Play `com.block.juggle`](https://play.google.com/store/apps/details?id=com.block.juggle) |
| Zawsze **trzy** kształty w tacce na dole | [blockblast.com](https://www.blockblast.com/) |
| **Klocków nie da się obracać** | [blockblast.com](https://www.blockblast.com/) — „pieces cannot be rotated; therefore, careful planning is crucial" |
| **Brak timera** | [blockblast.com](https://www.blockblast.com/) |
| Pełny wiersz **lub kolumna** znika, dając punkty | [blockblast.com](https://www.blockblast.com/) |
| Koniec gry, gdy nie da się postawić żadnego klocka | [blockblast.com](https://www.blockblast.com/) |
| Deweloper: Hungry Studio (ARETIS LIMITED) | [App Store](https://apps.apple.com/us/app/block-blast/id1617391485) |

### [F] Czego wydawca NIE podaje

Przeszukane materiały oficjalne **nie zawierają żadnej liczby**: ani punktów za
postawienie, ani za linię, ani mnożników combo, ani opisu generatora. Opis marketingowy
ogranicza się do:

> „Chase Combos: Plan your moves to unlock massive points and extend your endless high score run."
> — [App Store, opis dewelopera](https://apps.apple.com/us/app/block-blast/id1617391485)

To jest **jedyna** oficjalna wzmianka o combo i nie ma w niej żadnej semantyki liczbowej.

> **[D]** Brak publikacji reguł punktacji w grze typu *endless high score* jest normą
> branżową, nie sygnałem oszustwa. Ale oznacza, że **każdy** wzór krążący w sieci jest
> z definicji rekonstrukcją, a nie cytatem — łącznie z tymi poniżej.

---

## 2. Punktacja — najmocniejszy dostępny dowód

### 2.1 [F] Dwie niezależne reimplementacje zbiegają się na tym samym wzorze

To najważniejsze ustalenie tego biletu. Dwa niepowiązane projekty RL, pisane w różnych
językach, przez różnych autorów, zawierają **matematycznie identyczny** wzór na
czyszczenie linii.

**Źródło A — [`snickrscodes/Block-Blast-AI`](https://github.com/snickrscodes/Block-Blast-AI)**
(silnik bitboardowy w C++)

`bbengine/src/engine.h`, linie 17–22:

```cpp
inline constexpr std::array<int, 16> LINE_BONUS = []{
  ...
    a[i] = i * ((i > 1) ? (i - 1) : 1) * 10;
```

`bbengine/src/engine.cpp`, linie 59–77:

```cpp
  u64 new_ctr = ctr - 1;
  u64 new_combo = combo;
  int reward = (int)T.block_pop[bid];          // punkty za postawienie = liczba komórek
  if (lines) {
    new_combo++;                                // combo rośnie o 1
    new_ctr = 3 + (b0 != b2) + (b1 != b2);      // reset licznika wygaśnięcia
    reward += (int)new_combo * LINE_BONUS[lines];   // COMBO JEST MNOŻNIKIEM
  } else if (ctr == 1) {
    new_ctr = 3;
    new_combo = 0;                              // combo ginie dopiero tutaj
  }
  ...
  if (new_board == 0ull) reward += 300;         // pusta plansza
```

**Źródło B — [`RisticDjordje/BlockBlast-Game-AI-Agent`](https://github.com/RisticDjordje/BlockBlast-Game-AI-Agent)**
(reimplementacja w Pythonie)

`blockblast_game/game_state.py`:

```python
bonus = lines_cleared * 10 * (self.combos[1] + 1)
if lines_cleared > 2:
    bonus *= lines_cleared - 1
...
if all_clear:
    bonus += 300
```

oraz:

```python
self.MAX_COMBO_STREAK = 3   # Combo resets after this many placements without clears
```

**Zestawienie — wychodzi to samo:**

| ℓ (linie naraz) | Źródło A: `(c+1)·ℓ·(ℓ>1?ℓ−1:1)·10` | Źródło B: `ℓ·10·(c+1)`, ×`(ℓ−1)` gdy `ℓ>2` | zgodne? |
|---|---|---|---|
| 1 | 10·(c+1) | 10·(c+1) | ✅ |
| 2 | 20·(c+1) | 20·(c+1) | ✅ |
| 3 | 60·(c+1) | 60·(c+1) | ✅ |
| 4 | 120·(c+1) | 120·(c+1) | ✅ |
| 5 | 200·(c+1) | 200·(c+1) | ✅ |
| 6 | 300·(c+1) | 300·(c+1) | ✅ |
| pusta plansza | +300 | +300 | ✅ |

> **[D]** Zbieżność do ostatniej cyfry w dwóch niezależnych bazach kodu jest
> nieprzypadkowa. Albo obaj autorzy zmierzyli to samo zachowanie apki, albo jeden
> skopiował drugiego (nie znalazłem śladu cytowania w żadną stronę). Traktuję to jako
> **najlepszą dostępną hipotezę roboczą**, wciąż nie jako pomiar.

### 2.2 [P] Niezależne potwierdzenie z poradników — na dwóch punktach

Strony-farmy SEO (niska wiarygodność, brak metodyki) powtarzają dwie liczby, które
**dokładnie pasują** do wzoru `10·ℓ·(ℓ−1)`:

> „At 5 lines cleared, you earn a massive 200-point bonus, and clearing 6 or more lines
> in one move awards the maximum 300-point bonus."
> — [blockpuzzlesolver.com/scoring](https://blockpuzzlesolver.com/scoring/)

`10·5·4 = 200` ✅ i `10·6·5 = 300` ✅.

Te same strony potwierdzają **multiplikatywną** naturę combo:

> „A single clear at combo x8 is worth approximately 8× what it would have been with no
> combo active."
> — [onlineblockblastsolver.com/block-blast-score-rules](https://onlineblockblastsolver.com/block-blast-score-rules/)

oraz punkty za samo postawienie proporcjonalne do rozmiaru klocka:

> „Placing a 3x3 square gives you 9 points, while placing a small 1x1 block gives you 1 point."
> — [blockblastsolverss.com/block-blast-high-score](https://blockblastsolverss.com/block-blast-high-score/)

co zgadza się z `reward = T.block_pop[bid]` w źródle A.

> **[D]** Zbieżność plotki z kodem na trzech niezależnych punktach (200/300, mnożnik ×c,
> 1 pkt za komórkę) podnosi zaufanie do wzoru. Ale zbieżność plotki z kodem może też
> oznaczać, że plotka pochodzi z kodu — kierunku przepływu nie da się tu ustalić.

### 2.3 [P] Konkurencyjny model: „10 punktów za każdą usuniętą komórkę"

Istnieje **inny, niezgodny** model krążący po poradnikach:

> „Each block that gets cleared as part of a completed row or column contributes a fixed
> base amount, commonly cited as 10 points per block"
> — z tabelą: 1 linia = 80 pkt, 5 linii = 400 pkt + „około 200" bonusu,
> 6+ = 480+ pkt + „około 300" bonusu
> — [blockblastsolve.com/block-blast-scoring-formula](https://blockblastsolve.com/block-blast-scoring-formula/)

Ta sama strona sama się dyskwalifikuje:

> „A note on precision: exact bonus figures for 5+ line clears and board clears vary
> somewhat between game versions, platforms, and sources reporting them… Treat the higher
> tiers as directional rather than gospel."

> **[D]** Model „10 × usunięte komórki" daje 80 pkt za jedną linię zamiast 10 — różnica
> ośmiokrotna, nie do pogodzenia ze źródłami A i B. Co ciekawe, **człon bonusowy jest
> ten sam** (200/300). Możliwa reinterpretacja: pełny wzór to
> `10·usunięte_komórki + c·10·ℓ·(ℓ−1)`, a źródła A i B pominęły pierwszy człon.
> To rozstrzygalne **jednym pomiarem** na żywej apce (patrz §6, R1) i dlatego nie
> zgaduję dalej.

### 2.4 [F] Autor źródła A sam ostrzega, że apka nie jest stacjonarna

To jest ustalenie, które trzeba wziąć poważnie, bo pochodzi od osoby, która najgłębiej
w tym siedziała. README `snickrscodes/Block-Blast-AI`:

> „The simulator scoring system was reverse-engineered from the high-combo scoring
> behavior observed during the original development period."

> „Current real-game scores are not treated as directly comparable to the fixed simulator
> benchmark" — z powodu **„different multipliers across nearby versions"**,
> **„different scoring regimes after restarting games"** i **„apparent changes even within
> individual games"**.

> „The underlying mechanism is unknown and should not be assumed to depend only on app version."

> **[D]** To sugeruje **konfigurację serwerową / A-B testy punktacji** — czyli że pytanie
> „jaki jest wzór Block Blasta" może nie mieć jednej odpowiedzi. Jeżeli to prawda, most
> do oryginału musi logować wersję apki i identyfikator sesji, bo inaczej pomiary z
> różnych dni będą niespójne bez wyjaśnienia. To najpoważniejsze ryzyko dla całego
> pomysłu kalibracji symulatora pod oryginał.

### 2.5 Sporne: jak rośnie licznik combo

| Pytanie | Źródło A | Źródło B |
|---|---|---|
| Przyrost combo po czyszczeniu | `new_combo++` — **zawsze o 1** | `self.combos[1] += lines_cleared` — **o liczbę linii** |
| Punkty za samo postawienie | tak, `block_pop` (liczba komórek) | **nie ma ich wcale** |

> **[D]** Źródła rozjeżdżają się dokładnie w dwóch miejscach. Przy `ℓ=1` (najczęstszy
> przypadek) obie wersje dają to samo, więc rozbieżność ujawnia się dopiero przy
> wielokrotnych czyszczeniach — i tam różnica w wyniku końcowym jest ogromna.
> Nierozstrzygalne bez pomiaru.

### 2.6 [P] vs [F] — konflikt o wygasanie combo

To najciekawszy konflikt w całym badaniu.

**Farmy SEO twierdzą zgodnie, że combo ginie natychmiast:**

> „The combo counter — and the score multiplier attached to it — resets to zero the moment
> you place a piece without triggering any line clear."
> — [blockpuzzlesolver.com/scoring](https://blockpuzzlesolver.com/scoring/)

**Oba kody twierdzą coś przeciwnego.** Źródło A: 3-bitowy licznik wygaśnięcia
(`CTR_MASK`, bity 37–39 w `meta`), resetowany do `3 + (b0!=b2) + (b1!=b2)`, czyli
3/4/5 zależnie od tego, ile klocków zostało w tacce; combo ginie dopiero gdy licznik
spadnie do 1. Źródło B: `MAX_COMBO_STREAK = 3`, jawny komentarz
*„Combo resets after this many placements without clears"*.

Za wersją „combo przeżywa" przemawiają też raporty graczy o „bugu" z combo:

> „You may plan a three-move streak, but after two moves, the combo ends."
> — [onlineblockblastsolver.com/block-blast-glitch](https://onlineblockblastsolver.com/block-blast-glitch/)

> **[D]** Gracze opisujący, że combo „kończy się po dwóch ruchach zamiast po trzech",
> opisują mechanikę **z licznikiem** — gdyby combo ginęło natychmiast, nikt nie planowałby
> trzyruchowej serii bez czyszczenia. Stawiam, że wersja z licznikiem jest bliższa
> prawdzie, a farmy SEO po prostu przepisują od siebie nawzajem uproszczenie. Ale to
> **domysł**, oparty na spójności mechanizmu, nie na pomiarze.

---

## 3. Dobór trzech klocków

### 3.1 [F] Nie ma ŻADNEGO publicznego pomiaru na oficjalnej apce

Szukałem: dekompilacji IL2CPP konkretnie dla `com.block.juggle`, logów rozgrywek,
analiz statystycznych rozkładu klocków, wątków z danymi. **Nie znalazłem nic.**
Wyszukiwania po dekompilacji zwracają wyłącznie ogólne poradniki „jak reverse-engineerować
gry Unity/IL2CPP" — [Il2CppInspector](https://github.com/djkaty/Il2CppInspector),
[Il2CppDumper-based workflows](https://gist.github.com/BadMagic100/47096cbcf64ec0509cf75d48cfbdaea5) —
bez ani jednego opracowania dotyczącego tej gry.

> **To jest wynik negatywny i należy go zapisać jako taki: pytanie biletu o generator
> jest publicznie nierozstrzygnięte.**

### 3.2 [F] Co robi najlepsza implementacja referencyjna — i dlaczego to nie dowód

Źródło A losuje **jednostajnie**, `bbengine/src/env.h`, linie 27–38:

```cpp
inline int rand_block_pose(SplitMix64& rng, const Tables& T) noexcept {
  const u64 r0 = rng.next_u64();
  const int canon = (int)(r0 % Tables::N_CANON);     // 1/15 na typ kanoniczny
  const int base = (int)T.pose_off[canon];
  const int npose = (int)T.pose_off[canon + 1] - base;
  if (npose <= 1) return base;
  const u64 r1 = rng.next_u64();
  return base + (int)(r1 % (u64)npose);              // 1/n_b na orientację
}
```

wywoływane trzy razy niezależnie (`env.cpp:41–43`). Bez świadomości planszy,
bez gwarancji grywalności tacki.

> **[D]** To jest **założenie modelowe autora**, nie pomiar. Jednostajność jest
> naturalnym wyborem dla treningu RL (stacjonarny MDP), więc fakt, że ktoś ją wybrał,
> nie mówi nic o oryginale. Nie wolno tego cytować jako dowodu.

### 3.3 [F] Reimplementacje, które uznały jednostajność za NIEwystarczającą

Źródło B, `blockblast_game/game_state.py`, `generate_valid_shapes()`:

```python
"""
Greedily pick 3 shapes so each one can be placed on the board
"""
```

— generator **świadomy planszy**, gwarantujący grywalność każdego z trzech klocków.

Klon przeglądarkowy BlockBlastPlay opisuje **własny** kod (i to jest dla *tego* kodu
źródło pierwotne):

> „Every turn, the generator deals three pieces from a fixed library of 34 shapes…
> The selection is weighted: how full the board currently is changes the odds for each
> shape, and the generator also runs board-aware logic before a tray is dealt."

> „as fill increases past defined thresholds, pieces of 3 cells or fewer become more
> likely and pieces of 6 cells or more become substantially less likely."

> „the generator actively attempts to produce a three-piece tray that can be played in
> sequence… using a bounded number of candidate sets, and if none of them pass the full
> sequential-playability check, it falls back to a weaker check."

— [blockblastplay.com/is-block-blast-rigged](https://blockblastplay.com/is-block-blast-rigged/)

**Ta sama strona jawnie odcina się od wniosków o oryginale:**

> „Everything above this section describes BlockBlastPlay's own browser build, verified
> from its own source code. Hungry Studio's official mobile app is a separate
> implementation…"

> „the public official materials reviewed for this page do not disclose how the official
> app's internal piece-selection algorithm works — whether it is uniform, weighted, or
> board-aware."

> „…adaptive, skill-targeted difficulty in the official app is a widely reported player
> theory built on real frustration — not a confirmed mechanism."

> **[D]** Wzór jest wymowny: **każdy, kto budował grywalny klon, dorzucał świadomość
> planszy** (źródło B, BlockBlastPlay), a jednostajność została tylko tam, gdzie
> potrzebny był czysty MDP do treningu (źródło A). To nie dowodzi, że oryginał jest
> adaptacyjny — ale sugeruje, że jednostajne losowanie daje odczucia rozgrywki
> odbiegające od oryginału na tyle, że praktycy je porzucali.

### 3.4 [P] „Czy Block Blast jest ustawiony?"

Powszechna teoria graczy: po dobrym wyniku gra „nagle się zacina". Brak jakiegokolwiek
dowodu. Kontrargument, który uważam za rzetelny:

> Użyteczność klocka zależy silnie od stanu planszy — duży klocek L bywa bezużyteczny na
> jednej planszy i idealny na innej — więc odczuwane „ustawienie" może odzwierciedlać
> interakcję klocka z układem planszy, a nie celową manipulację.
> — [playgama.com/blog/game-faqs](https://playgama.com/blog/game-faqs/why-do-people-think-block-blast-is-rigged/)

### 3.5 [F] Zbiór kształtów według źródła A: 15 typów, 41 orientacji

`bbengine/src/tables.h`, linie 15–22 — 15 masek bitowych. Po zdekodowaniu i zamknięciu
na grupę D4 (dedup do 41 poz, sprawdzane asercją `if (pose_off[N_CANON] != N_BLOCKS) die();`):

| Typ | Komórki | Orientacje |
|---|---|---|
| 1×1 | 1 | 1 |
| belka 1×2 | 2 | 2 |
| belka 1×3 | 3 | 2 |
| belka 1×4 | 4 | 2 |
| **belka 1×5** | 5 | 2 |
| kwadrat 2×2 | 4 | 1 |
| prostokąt 2×3 | 6 | 2 |
| kwadrat 3×3 | 9 | 1 |
| narożnik L (tromino) | 3 | 4 |
| L/J (tetromino) | 4 | 8 |
| **duży narożnik L (3×3)** | 5 | 4 |
| **przekątna 2** | 2 | 2 |
| **przekątna 3** | 3 | 2 |
| S/Z | 4 | 4 |
| T | 4 | 4 |
| **razem** | | **41** |

Istnienie klocków 5-komórkowych (1×5) potwierdzają niezależnie poradniki:
„The 3x3, 2x3, and 1x5 pieces" — [smartblockblastsolver.com](https://smartblockblastsolver.com/blogs/block-blast-pieces) **[P]**.

Uwaga: BlockBlastPlay mówi o **34** kształtach we własnym buildzie — inna liczba niż 41.
Żadna z tych liczb nie jest zmierzona na oryginale. **[F/D]**

---

## 4. Rozbieżności wobec naszego symulatora

Porównanie stanu na gałęzi `main` (`scoring.py`, `generator.py`, `pieces.py`, `board.py`,
`game.py`) z modelem referencyjnym z §2.1 i §3.5.

### R-1 — Wzór na jednoczesne czyszczenie: zawyżamy przy ℓ≥2

`scoring.py:8` → `simultaneous_clear_points(k) = 10·k²`
Referencja → `10·ℓ·(ℓ−1)` dla `ℓ≥2`, `10` dla `ℓ=1`.

| ℓ | my (`10k²`) | referencja | błąd |
|---|---|---|---|
| 1 | 10 | 10 | — |
| 2 | 40 | 20 | **+100%** |
| 3 | 90 | 60 | **+50%** |
| 4 | 160 | 120 | +33% |
| 5 | 250 | 200 | +25% |
| 6 | 360 | 300 | +20% |

Systematycznie przepłacamy za multi-clear, najmocniej za podwójne — czyli za ruch, który
agent wykonuje najczęściej.

### R-2 — Combo jest u nas ADDYTYWNE, a powinno być MNOŻNIKIEM

`scoring.py:11` → `streak_bonus(streak) = 10·(streak−1)`, doliczane **obok** punktów
za czyszczenie (`game.py:102`).
Referencja → `reward += (c+1) · LINE_BONUS[ℓ]`, combo **mnoży** cały bonus za czyszczenie.

To nie jest różnica kalibracji, tylko **inny kształt funkcji nagrody**. U nas seria
20 czyszczeń daje `+190` łącznie; w modelu referencyjnym samo 20. czyszczenie jednej
linii daje `20 × 10 = 200`. Nasz agent nie ma powodu, by ścigać długie serie — a to jest
**główna oś gry** według opisu wydawcy („Chase Combos… unlock massive points").

> **[D]** To prawdopodobnie najpoważniejsza rozbieżność w repo: uczymy agenta gry,
> w której combo praktycznie nie istnieje.

### R-3 — Combo liczymy raz na TACKĘ, a nie raz na POSTAWIENIE

`game.py:93–103`: `streak` aktualizuje się **wyłącznie gdy `round_placement == 3`**,
czyli raz na trzy klocki, na podstawie `last_lines_cleared` skumulowanego z całej tacki.
Referencja (oba źródła): combo aktualizuje się **po każdym postawieniu**.

Konsekwencja: u nas postawienie klocka bez czyszczenia **nie przerywa** serii, jeśli
któryś z pozostałych dwóch klocków w tacce czyścił. To zupełnie inna dynamika niż
licznik wygaśnięcia z §2.6.

### R-4 — Brak mechanizmu wygasania combo

Nie mamy odpowiednika 3-bitowego licznika (źródło A) ani `MAX_COMBO_STREAK` (źródło B).
Nasz `streak` zeruje się twardo na koniec tacki bez czyszczenia (`game.py:99`).

### R-5 — Bonus za pustą planszę: 100 zamiast 300

`game.py:89` → `this_round_score += 100`.
Oba źródła referencyjne → **+300**. (Farma SEO podaje jeszcze inną liczbę, 360 — patrz §5.)
Dodatkowo `game.py:90` przyznaje **`reward += 1000`** do sygnału RL, co jest
rozjazdem między wynikiem gry a nagrodą agenta — prawdopodobnie celowym, ale nieopisanym.

### R-6 — Pula klocków pokrywa 39% referencyjnych orientacji

Nasze 16 unikalnych kształtów to **podzbiór** 41 poz referencyjnych (żadnego kształtu
nadmiarowego), ale **brakuje 25 poz (61%)**:

- **całego typu 1×5 / 5×1** — najdłuższa belka w grze, kluczowa dla czyszczenia linii;
- **całego typu przekątna-2 i przekątna-3**;
- **całego typu narożnik-L 3-komórkowy** (`((1,1),(1,0))` i 3 obroty);
- **całego typu duży narożnik L 5-komórkowy** (3×3 corner, 4 obroty);
- **większości obrotów** J/L (mamy 2 z 8), T (1 z 4), S/Z (2 z 4).

Ponieważ gra **nie pozwala obracać klocków** ([F], §1), brakujące orientacje to realnie
brakujące klocki, a nie kosmetyka.

Uwaga łagodząca: średni rozmiar klocka wychodzi niemal identycznie
(**4,00** u nas vs **3,93** w modelu type-uniform referencyjnym), więc presja wypełniania
planszy jest podobna — rozjeżdża się *kształt* trudności, nie jej skala.

### R-7 — Duplikat w puli zaburza rozkład

`pieces.py` ma **17 wpisów, ale 16 unikalnych kształtów**: `"O"` (`[[1,1],[1,1]]`) i
`"2x2"` (`[[1,1],[1,1]]`) to ten sam klocek. Skutek: kwadrat 2×2 wypada z
prawdopodobieństwem **2/17**, każdy inny **1/17** — niezamierzone, nieudokumentowane
obciążenie generatora.

### R-8 — Rozkład: my jednostajnie po POZACH, referencja jednostajnie po TYPACH

`generator.py:17` → `self.rng.choice(PIECE_POOL)` — jednostajnie po wpisach puli.
Referencja → najpierw `1/15` na typ kanoniczny, **potem** `1/n_b` na orientację.

To dwa różne rozkłady. W modelu referencyjnym klocek o 8 orientacjach (L/J) ma każdą
pozę z p = 1/120, a klocek 3×3 (1 orientacja) ma p = 1/15 — **ośmiokrotnie więcej**.
U nas wszystkie pozy są równoprawne. Nawet gdyby nasza pula była kompletna, rozkład
byłby inny.

### R-9 — `Generator` nazywa się „Deterministic", ale ignoruje ziarno

`generator.py:8–14`:

```python
def __init__(self, seed=None):
    self.seed = seed
    self.rng = random.Random()      # seed NIE jest przekazany

def reset(self, seed=None):
    self.seed = seed
    self.rng = random.Random()      # to samo
```

Docstring pliku brzmi `"""Deterministic Piece Generator"""`. Ziarno jest zapisywane do
`self.seed` i **nigdy nieużywane**. Powtarzalne przebiegi ewaluacyjne są w tej chwili
niemożliwe. To bug niezależny od pytania badawczego, ale blokujący każdy pomiar
porównawczy — w tym kalibrację pod oryginał.

### R-10 — Martwy kod: `Generator.generate_board`

`generator.py:19–32` buduje losową planszę (wypełnia wszystko jedynkami, wycina klocki,
potem zeruje ~33% komórek). Nie jest wywoływane z `game.py`.

> **[D]** Zgodnie z zasadą „usuwaj" (krok 2): jeśli to narzędzie diagnostyczne, jego
> miejsce jest w testach; jeśli pozostałość — do wycięcia. Nie optymalizować, nie
> dokumentować — usunąć albo przenieść.

### Czego NIE trzeba zmieniać

- **`board.py` jest zgodny z referencją.** Plansza 8×8 [F], czyszczenie wierszy
  *i* kolumn [F], brak rotacji klocków (`place_piece` nie zna obrotów) [F],
  jednoczesne wykrywanie pełnych linii przed czyszczeniem — wszystko się zgadza.
  Nie ruszać.
- **Punkty za postawienie = liczba komórek** (`scoring.py:5`) zgadzają się ze źródłem A
  (`block_pop`) i z [P] („3x3 → 9 punktów, 1x1 → 1 punkt"). Jedyna wątpliwość: czy nie
  powinno być ×10 (§2.3). Nie zmieniać bez pomiaru.
- **Tacka trzech klocków odnawiana dopiero po wyczerpaniu** (`game.py:104–105`) jest
  zgodna z opisem wydawcy [F].

---

## 5. Twierdzenia sprzeczne — świadomie nierozstrzygnięte

| Pytanie | Wersja 1 | Wersja 2 | Status |
|---|---|---|---|
| Bonus za pustą planszę | **300** (oba kody, [F]) | **360** ([blockpuzzlesolver.com](https://blockpuzzlesolver.com/scoring/), [P]) | nierozstrzygnięte |
| Combo po czyszczeniu rośnie o… | **1** (źródło A) | **liczbę linii** (źródło B) | nierozstrzygnięte |
| Combo ginie… | po **1** postawieniu bez czyszczenia ([P], farmy SEO) | po **3–5** (oba kody, [F]) | nierozstrzygnięte, skłaniam się ku kodom |
| Punkt bazowy za czyszczenie | **10 za linię** (oba kody) | **10 za usuniętą komórkę** → 80/linię ([blockblastsolve.com](https://blockblastsolve.com/block-blast-scoring-formula/), [P]) | nierozstrzygnięte |
| Bonus przy ℓ≥7 | `10·ℓ·(ℓ−1)` rośnie dalej (tablica do 16, źródło A) | „6+ = maksimum 300" ([P]) | nierozstrzygnięte |
| Liczba kształtów | **15 typów / 41 poz** (źródło A) | **34** (build BlockBlastPlay) | oba to reimplementacje |
| Generator | jednostajny (źródło A) | świadomy planszy (źródło B, BlockBlastPlay) | **brak pomiaru oryginału** |

> **[D]** Nie wybieram zwycięzcy w żadnym z tych wierszy. Każdy z nich to konkretne,
> tanie zapytanie pomiarowe — patrz §6.

---

## 6. Czego nie da się ustalić bez pomiarów na żywej apce

To jest lista wymagań do biletu o **most do oryginału** (przechwytywanie stanu i wyniku
z działającej instalacji Block Blast). Uporządkowane od najtańszego/najbardziej
rozstrzygającego.

### Punktacja

- **R1 — Jednostka punktu bazowego.** Postawić klocek czyszczący **dokładnie 1 linię**
  przy combo = 0 i odczytać przyrost wyniku. `10` → wygrywa model kodowy;
  `80` (lub `10 × usunięte komórki`) → wygrywa model z §2.3. **Jeden ruch rozstrzyga
  największą otwartą niewiadomą.** Priorytet najwyższy.
- **R2 — Czy postawienie bez czyszczenia daje punkty i ile.** Postawić 1×1, 1×2, 3×3
  bez czyszczenia; sprawdzić, czy przyrost to `n`, `10n`, czy `0`. Rozstrzyga spór
  źródło A vs źródło B.
- **R3 — Tabela bonusu dla ℓ = 1…5 przy combo = 0.** Daje wzór `B(ℓ)` bezpośrednio,
  bez zakładania jego postaci. Potwierdza lub obala `10·ℓ·(ℓ−1)`.
- **R4 — Czy combo mnoży, czy dodaje.** To samo czyszczenie 1 linii przy combo = 0, 1, 2, 5.
  Liniowy wzrost `∝ (c+1)` → mnożnik; stały przyrost → model addytywny (nasz).
- **R5 — Krok inkrementacji combo.** Wyczyścić 3 linie jednym ruchem i odczytać licznik
  combo w UI: `+1` czy `+3`.
- **R6 — Długość wygasania combo.** Zbudować combo, potem stawiać klocki **bez**
  czyszczenia i policzyć, po ilu postawieniach licznik spada do zera. Sprawdzić, czy
  wynik zależy od liczby klocków pozostałych w tacce (hipoteza `3 + pozostałe` ze
  źródła A).
- **R7 — Bonus za pustą planszę.** Doprowadzić do pustej planszy, odczytać przyrost:
  300, 360, czy coś innego. Sprawdzić, czy bonus jest mnożony przez combo.
- **R8 — Zachowanie przy ℓ ≥ 6.** Czy `B(ℓ)` nasyca się na 300, czy rośnie dalej.
- **R9 — Sufit combo.** Czy mnożnik jest ograniczony (np. ×8, ×10), czy rośnie bez końca.
- **R10 — Stacjonarność (§2.4).** **Powtórzyć R1–R4 w trzech oddzielnych sesjach,
  w trzech różnych dniach, na tej samej wersji apki.** Jeśli liczby się różnią,
  punktacja jest konfigurowana serwerowo i cała kalibracja wymaga innego podejścia.
  Logować: wersję apki, datę, identyfikator instalacji. **To jest wymaganie blokujące —
  jeśli wynik wyjdzie niestacjonarny, bilety o kalibrację punktacji tracą sens
  w obecnej formie.**

### Dobór klocków

- **R11 — Pełny inwentarz kształtów.** Logować każdą tackę przez ≥ 5000 klocków.
  Ustalić zamknięty zbiór typów i orientacji. Rozstrzyga 41 vs 34 vs nasze 16.
- **R12 — Test jednostajności.** Na tych samych danych: test χ² zgodności z rozkładem
  jednostajnym po typach oraz po pozach. Rozstrzyga §3 raz na zawsze.
- **R13 — Zależność od zapełnienia planszy.** Skorelować rozmiar wylosowanego klocka
  z liczbą zajętych komórek w chwili losowania. Hipoteza do obalenia:
  „przy wysokim zapełnieniu rosną szanse klocków ≤ 3 komórek" (opis własnego buildu
  BlockBlastPlay, §3.3).
- **R14 — Gwarancja grywalności tacki.** Policzyć, ile razy wystąpiła tacka, w której
  **żadnego** klocka nie da się postawić, oraz ile razy tacka **nie dała się rozegrać
  w całości** (3 klocki po kolei). Zero wystąpień na dużej próbie → generator ma
  zabezpieczenie.
- **R15 — Niezależność trzech losowań w tacce.** Test niezależności na parach
  (klocek₁, klocek₂) w obrębie tacki. Odrzucenie niezależności → tacka jest dobierana
  jako całość, nie trzema niezależnymi losowaniami.
- **R16 — Zależność od wyniku/serii (teoria „rigged").** Skorelować rozmiar/użyteczność
  klocka z bieżącym wynikiem i długością combo. To jedyny test, który może potwierdzić
  lub obalić teorię adaptacyjnej trudności — dotąd **nikt publicznie go nie wykonał**
  (§3.1). Wymaga długich sesji i grupy kontrolnej (gra losowa vs gra silna).

### Wymagania niefunkcjonalne dla mostu

- Musi rejestrować **stan planszy przed ruchem, postawiony klocek i pozycję, przyrost
  wyniku, licznik combo z UI i zawartość tacki** — w jednym rekordzie na postawienie.
  Bez sprzężenia „ruch → przyrost" żaden z testów R1–R9 nie jest wykonalny.
- Musi logować **wersję apki** przy każdej sesji (R10).
- Musi działać bez modyfikacji APK, żeby nie zmieniać zachowania mierzonego systemu.

---

## 7. Wpływ na założenia mapy

- **Nie unieważnia mapy.** Bilet zakładał, że `scoring.py` i `generator.py` to
  rekonstrukcje — i to się potwierdziło w całej rozciągłości.
- **Jedno założenie wymaga rewizji:** most do oryginału był traktowany jako narzędzie
  do *zmierzenia stałych*. Ostrzeżenie z §2.4 („different multipliers across nearby
  versions… apparent changes even within individual games") sugeruje, że stałych
  **może nie być**. Most musi najpierw odpowiedzieć na R10 (stacjonarność), zanim
  cokolwiek innego z niego wyciągniemy.
- **Nowa informacja, której mapa nie przewidywała:** rozbieżność R-2/R-3 (combo
  addytywne i liczone na tackę zamiast mnożnika liczonego na postawienie) jest
  rozbieżnością **kształtu funkcji nagrody**, nie kalibracji. Dotychczasowe wyniki
  treningu agenta opisują grę, w której pogoń za combo się nie opłaca — a to według
  opisu wydawcy jest główna mechanika. Warto to rozważyć przy interpretacji
  `training_stats*.csv`.

---

## Źródła

**Pierwotne — kod (najwyższe zaufanie dla *tej* implementacji, nie dla oryginału)**

- [snickrscodes/Block-Blast-AI](https://github.com/snickrscodes/Block-Blast-AI) —
  `bbengine/src/engine.h`, `engine.cpp`, `env.h`, `env.cpp`, `tables.h`, README
- [RisticDjordje/BlockBlast-Game-AI-Agent](https://github.com/RisticDjordje/BlockBlast-Game-AI-Agent) —
  `blockblast_game/game_state.py`

**Pierwotne — wydawca**

- [App Store: Block Blast!](https://apps.apple.com/us/app/block-blast/id1617391485)
- [Google Play: com.block.juggle](https://play.google.com/store/apps/details?id=com.block.juggle)
- [blockblast.com](https://www.blockblast.com/) · [hungrystudio.com](https://hungrystudio.com/)

**Pierwotne dla cudzego klona (nie dla oryginału)**

- [blockblastplay.com/is-block-blast-rigged](https://blockblastplay.com/is-block-blast-rigged/)

**Wtórne / plotka — cytowane wyłącznie jako [P]**

- [blockpuzzlesolver.com/scoring](https://blockpuzzlesolver.com/scoring/)
- [blockblastsolve.com/block-blast-scoring-formula](https://blockblastsolve.com/block-blast-scoring-formula/)
- [onlineblockblastsolver.com/block-blast-score-rules](https://onlineblockblastsolver.com/block-blast-score-rules/)
- [onlineblockblastsolver.com/block-blast-glitch](https://onlineblockblastsolver.com/block-blast-glitch/)
- [blockblastsolverss.com/block-blast-high-score](https://blockblastsolverss.com/block-blast-high-score/)
- [smartblockblastsolver.com/blogs/block-blast-pieces](https://smartblockblastsolver.com/blogs/block-blast-pieces)
- [playgama.com/blog/game-faqs — why rigged](https://playgama.com/blog/game-faqs/why-do-people-think-block-blast-is-rigged/)

**Metodyka dekompilacji (na przyszłość, brak opracowań dla tej gry)**

- [djkaty/Il2CppInspector](https://github.com/djkaty/Il2CppInspector)
- [BadMagic100— il2cpp decompilation notes](https://gist.github.com/BadMagic100/47096cbcf64ec0509cf75d48cfbdaea5)
