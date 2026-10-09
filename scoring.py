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


# Mnożnik bonusu za czyszczenie maleje z wynikiem partii (wynik sprzed ruchu), ale tylko w partiach o niskim tempie
# punktów na postawienie. Progi z logów faza0, ruch po ruchu (partie 4, 8, 10): 100% do 5991-6076, 80% od 6077
# (6447 jeszcze 80%), 60% od 6607 (7123 jeszcze 60%), 40% od 7203 (8251 jeszcze 40%), 30% od 8409. Te same progi
# w trzech partiach. Partie 3 i 9 (powyżej 6000 pkt już po 59 i 67 postawieniach, 106-112 pkt na postawienie)
# mają 100% przez całą partię (do 29 tys.), partie 4, 8, 10 spadały przy 45-50 pkt na postawienie.
SCORE_DECAY = ((8409, 30), (7203, 40), (6607, 60), (6077, 80))
DECAY_MAX_RATE = 75   # spadek tylko, gdy wynik / liczba postawień < 75; granica leży w przedziale (50, 106)


# Przy zestawie kontrolnym (10 partii) spadek miała tylko część partii powyżej 6077 pkt i nie rozstrzyga o tym
# bieżące tempo: partie z tempem 73 i 86 pkt/postawienie w chwili przekroczenia progu spadały, partie z tempem 46,
# 66 i 142 nie. Dlatego tempo jest zatrzaskiwane raz, przy pierwszym przekroczeniu progu (patrz game.py), i mieści
# się w oknie [DECAY_MIN_RATE, DECAY_MAX_RATE_LATCH).
DECAY_MIN_RATE = 70
DECAY_MAX_RATE_LATCH = 110


def decay_latch(score, placements):
    """Czy partia przekraczająca pierwszy próg spadku w tym tempie (pkt/postawienie) podlega spadkowi."""
    return placements > 0 and DECAY_MIN_RATE * placements <= score < DECAY_MAX_RATE_LATCH * placements


def score_decay(score, placements=0, active=None):
    if active is False or (active is None and (placements <= 0 or score >= DECAY_MAX_RATE * placements)):
        return 100
    for threshold, percent in SCORE_DECAY:
        if score >= threshold:
            return percent
    return 100


def clear_points(combo, lines, score=0, placements=0, active=None):
    """Punkty za czyszczenie: combo (po inkrementacji) mnoży bonus bazowy w jednostce combo_unit."""
    return combo * line_bonus(lines) * combo_unit(combo) * score_decay(score, placements, active) // 1000
