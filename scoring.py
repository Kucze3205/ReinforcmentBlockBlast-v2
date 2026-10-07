"""
Block Blast Scoring System

Wzór referencyjny ustalony w badaniu #2 — zbieżny co do cyfry w dwóch
niezależnych reimplementacjach:

    punkty = liczba_komorek_klocka + combo_po_inkrementacji * B(l)
    B(l)   = 0 dla l=0,  10 dla l=1,  10*l*(l-1) dla l>=2
    + FULL_CLEAR_BONUS za opróżnienie planszy

Pomiar na apce (logi mostu faza0): od combo 6 mnożnik rośnie o połowę, od 11 podwaja się;
licznik wygaśnięcia 3 + tyle, ile klocków zostało w tacce (logi mostu: klocek z pustą resztą tacki przeżywa 2 postawienia bez czyszczenia).
Combo jest MNOŻNIKIEM całego bonusu za czyszczenie, nie dodatkiem (R-2).
Nic z tego nie jest pomiarem na oryginale — patrz docs/calibration-assumptions.md.
"""

FULL_CLEAR_BONUS = 0  # logi faza0, n=2: opróżnienie planszy dało tylko 3 + 20 punktów

# Ile postawień bez czyszczenia przeżywa combo, gdy tacka jest pusta/1/2 klocki.
COMBO_COUNTER_BASE = 3


# Jednorazowe premie za przekroczenie progu licznika (logi faza0: 472->982 i 499->901 to +400 przy 500,
# 986->3986 to +3000 przy ~1000, 4773->9047 to +4000 przy ~5000). Przy 1500, 2000, 2500... premii nie
# ma (pary 1427->1670, 1932->2214). Hipoteza dopasowana do logów, nie pomiar reguły oryginału.
SCORE_MILESTONES = ((500, 400), (1000, 3000), (5000, 4000))


def milestone_points(before, after):
    """Premie za progi przekroczone przy przejściu licznika z `before` do `after`."""
    return sum(bonus for threshold, bonus in SCORE_MILESTONES if before < threshold <= after)


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


def combo_multiplier_halves(combo):
    """Mnożnik combo w połówkach: x1 do combo 5, x1,5 dla 6-10, x2 od 11 (logi mostu: 10,20,..,50,90,105,..,150,220,240,..)."""
    if combo <= 5:
        return 2
    if combo <= 10:
        return 3
    return 4


def clear_points(combo, lines):
    """Punkty za czyszczenie: combo (po inkrementacji) razy mnożnik progu razy bonus bazowy."""
    return combo * combo_multiplier_halves(combo) * line_bonus(lines) // 2
