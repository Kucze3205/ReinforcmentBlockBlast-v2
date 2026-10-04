# Block Blast — agent grający w grę

Repozytorium niesie reimplementację gry Block Blast wraz z agentem, który się w nią
gra. Glosariusz opisuje cel agenta.

## Język

**Cel**:
Agent nie przegrywa. 1 mln punktów licznika apki to limit długości partii
ustalony przez właściciela, nie miara poziomu: partia, która do niego dotrwa,
dowodzi nieprzegrywania. Punkty są rozstrzygnięciem remisu, nigdy kosztem
przeżycia.
_Avoid_: 1 mln jako wynik do pobicia, „nasz wzór" jako licznik celu

**Przegrana**:
Koniec partii, bo żaden klocek z tacki nie mieści się na planszy — wina
algorytmu.
_Avoid_: śmierć (poza symulatorem), porażka, przerwanie
