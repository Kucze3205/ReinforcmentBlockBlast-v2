"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + combo_po_inkrementacji * B(l)
    B(l)   = 0 dla l=0,  10 dla l=1,  10*l*(l-1) dla l>=2
    + FULL_CLEAR_BONUS za opróżnienie planszy

Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).
Nic z tego nie jest pomiarem na oryginale — patrz docs/calibration-assumptions.md.
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


# Logi mostu (faza0, odcinek 150 ruchów): combo 1-5 zgadza się ze wzorem co do punktu, od combo 6 licznik apki
# daje 1,5-3x więcej (np. combo 10: 220 za linię zamiast 100). Mechanizmu nie znamy (kolor linii? poziom?),
# stała dopasowana tak, by suma punktów zgadzała się z licznikiem apki.
HIGH_COMBO_FROM = 6
HIGH_COMBO_FACTOR = 2.2


def clear_points(combo, lines):
    """Punkty za czyszczenie: combo (po inkrementacji) mnoży bonus bazowy."""
    points = combo * line_bonus(lines)
    if combo >= HIGH_COMBO_FROM:
        points = round(points * HIGH_COMBO_FACTOR)
    return points
