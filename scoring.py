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

# Najniższe combo, przy którym apka wypłaca bonus za pustą planszę (zmierzone w logach: combo 1 i 2 nie, 4 tak).
FULL_CLEAR_MIN_COMBO = 4

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


def combo_unit(combo):
    """Mnożnik jednostki bonusu rośnie ze streakiem: combo 1-5 -> 1, 6-10 -> 1,5, od 11 -> 2.

    Zmierzone na logach faza0: 1 linia daje 10*combo do combo 5, 15*combo dla 6-10 i 20*combo od 11.
    """
    if combo <= 5:
        return 10
    if combo <= 10:
        return 15
    return 20


# Mnożnik bonusu za czyszczenie maleje z łącznym wynikiem partii (procenty). Zmierzone na logach faza0
# (partie 1, 8, 9): 100% do ~6000 pkt, 80% od ~6000, 60% od ~6600, 40% od ~7000, 30% od ~8500;
# dalej 30% aż do 997 tys. pkt. Progi znane z dokładnością do przedziału między sąsiednimi ruchami.
SCORE_DECAY = ((8500, 30), (7000, 40), (6600, 60), (6000, 80))


def score_decay(score):
    for threshold, percent in SCORE_DECAY:
        if score >= threshold:
            return percent
    return 100


def clear_points(combo, lines, score=0):
    """Punkty za czyszczenie: combo (po inkrementacji) mnoży bonus bazowy w jednostce combo_unit."""
    return combo * line_bonus(lines) * combo_unit(combo) * score_decay(score) // 1000
