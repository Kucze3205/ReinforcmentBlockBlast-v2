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

# Najniższe combo, przy którym apka wypłaca bonus za pustą planszę (zmierzone w logach: combo 1, 2, 5 i 6 nie, 7+ tak).
FULL_CLEAR_MIN_COMBO = 1

# Najniższy wynik partii, od którego apka wypłaca bonus za pustą planszę (zmierzone: bez bonusu przy 148, 182, 301 pkt,
# z bonusem przy 482 pkt, combo 4; combo nie rozstrzyga). Próg znany z dokładnością do przedziału 301-482.
FULL_CLEAR_MIN_SCORE = 400

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


# Mnożnik bonusu za czyszczenie NIE zależy od wyniku partii: zmierzone na logach faza0, partie 2, 4 i 9 liczą 100% przy
# 6000-60000 pkt (np. faza0-9 n85-n104 przy 6283-8806 pkt, faza0-2 n72-n73 przy 6387-6890). Dawne progi 80/60/40/30%
# wynikały z rozjazdu combo, nie z punktacji; tylko dwa ruchy partii 10 (n108, n112 przy ~6100 pkt) dają 80%.
SCORE_DECAY = ()


def score_decay(score):
    for threshold, percent in SCORE_DECAY:
        if score >= threshold:
            return percent
    return 100


def clear_points(combo, lines, score=0):
    """Punkty za czyszczenie: combo (po inkrementacji) mnoży bonus bazowy w jednostce combo_unit."""
    return combo * line_bonus(lines) * combo_unit(combo) * score_decay(score) // 1000
