# Block Blast — agent grający w grę

Repozytorium niesie reimplementację gry Block Blast wraz z agentem, który się w nią
gra. Glosariusz opisuje cel agenta.

## Język

**Cel**:
Agent nie przegrywa. Seria 80 partii po 125 tys. punktów licznika apki (razem
10 mln) bez przegranej dowodzi nieprzegrywania. 125 tys. to limit długości partii
ustalony przez właściciela, nie miara poziomu: dziesięć partii po 1 mln nie mieściło
się w limicie czasu joba, a łączna liczba punktów bez przegranej jest ta sama (#48). Punkty są rozstrzygnięciem remisu, nigdy kosztem
przeżycia.
_Avoid_: cel partii jako wynik do pobicia, „nasz wzór" jako licznik celu

**Przegrana**:
Koniec partii, bo żaden klocek z tacki nie mieści się na planszy — wina
algorytmu.
_Avoid_: śmierć (poza symulatorem), porażka, przerwanie
