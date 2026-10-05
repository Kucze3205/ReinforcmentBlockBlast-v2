"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + M(combo_po_inkrementacji) * B(l)
    B(l)   = 0 dla l=0,  10 dla l=1,  10*l*(l-1) dla l>=2
    + FULL_CLEAR_BONUS za opróżnienie planszy

Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).

Kalibracja do logów mostu (faza0, 10 partii): M(c) = c tylko do c=4. Dalej apka płaci
więcej niż liniowo (bonus za 1 linię: c=5 -> 50, c=6 -> 90, c=22 -> 520, c=23 -> 540;
za 2 linie / 20: c=4 -> 5, c=5 -> 9, c=6 -> 12, c=10 -> 26, c=12 -> 30, c=21 -> 48).
M(c) poniżej to dopasowanie do tych punktów (od c=10 mniej więcej 2c+6), nie wzór z apki.
"""

FULL_CLEAR_BONUS = 300

# Ile postawień bez czyszczenia przeżywa combo, gdy tacka jest pusta/1/2 klocki.
COMBO_COUNTER_BASE = 3


# M(c) dla c = 0..9; od 10 wzrost o 2 na jedno combo.
COMBO_MULTIPLIER = (0, 1, 2, 3, 4, 9, 12, 16, 19, 22)


def combo_multiplier(combo):
    """M(c): mnożnik bonusu za czyszczenie przy combo c (po inkrementacji)."""
    if combo < len(COMBO_MULTIPLIER):
        return COMBO_MULTIPLIER[max(combo, 0)]
    return 2 * combo + 6


def placement_points(piece):
    """Punkty za samo postawienie = liczba komórek klocka."""
    return sum(int(cell) for row in piece.shape for cell in row)


def line_bonus(lines):
    """B(l) — bonus bazowy za wyczyszczenie l linii jednocześnie, przed mnożnikiem combo."""
    if lines <= 0:
        return 0
    if lines == 1:
        return 10
    return 10 * lines * (lines - 1)


def clear_points(combo, lines):
    """Punkty za czyszczenie: M(combo) (combo po inkrementacji) mnoży bonus bazowy."""
    return combo_multiplier(combo) * line_bonus(lines)
