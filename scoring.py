"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + combo_po_inkrementacji * B(l)
    B(l)   = 0 dla l=0,  10 dla l=1,  10*l*(l-1) dla l>=2
    + FULL_CLEAR_BONUS za opróżnienie planszy

Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).

Pomiar na oryginale (logi mostu, .zadanie/dane): do combo 5 wzór się zgadza co do cyfry,
od combo 6 apka płaci więcej: pojedyncza linia dawała bonus 90 przy combo 6, 260 przy 12,
300 przy 14, 380 przy 17, 500 przy 22, 600 przy 26, 700 przy 30, 880 przy 38
(czyli ok. 2,3 x 10 * combo w długiej serii). Dwie linie przy combo 16/20/24 dają
730/971/1129 = 20 * 36,5/48,5/56,5, czyli ten sam mnożnik. Mechanizm nie jest znany;
MULT_POINTS to interpolacja zmierzonych punktów (combo -> efektywny mnożnik).
"""

FULL_CLEAR_BONUS = 300

# Ile postawień bez czyszczenia przeżywa combo, gdy tacka jest pusta/1/2 klocki.
COMBO_COUNTER_BASE = 3


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


# (combo, efektywny mnożnik bonusu) zmierzone na oryginale; między punktami interpolacja liniowa.
MULT_POINTS = [(0, 0), (5, 5), (6, 9), (12, 26), (14, 30), (17, 38), (22, 46), (26, 60), (30, 70), (38, 88)]
MULT_SLOPE = 2.4  # nachylenie powyżej ostatniego punktu


def combo_multiplier(combo):
    if combo <= MULT_POINTS[-1][0]:
        for (c0, m0), (c1, m1) in zip(MULT_POINTS, MULT_POINTS[1:]):
            if combo <= c1:
                return m0 + (m1 - m0) * (combo - c0) / (c1 - c0)
    c, m = MULT_POINTS[-1]
    return m + MULT_SLOPE * (combo - c)


def clear_points(combo, lines):
    """Punkty za czyszczenie: efektywny mnożnik combo (po inkrementacji) razy bonus bazowy."""
    return round(combo_multiplier(combo) * line_bonus(lines))
