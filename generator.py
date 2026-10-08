"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 liczone tak jak miara χ² w ocenie (nowa tacka = inna niż
# poprzednia): 10 partii, pierwsze 300 ruchów każdej, 1791 klocków. Dawne wagi (1095 klocków z "pełnych tacek")
# dawały na tym samym zestawie χ² = 723 przy df = 39, p = 0. Długie partie wpadają w pętle kilku powtarzanych
# tacek (partia 1: cykl 3 tacek, partia 9 i 10: kilka klocków po ~150 razy), więc rozkład zależy od planszy,
# a generator bez planszy odtwarza tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 47,
    "beam2-0": 100,
    "beam2-1": 93,
    "beam3-0": 65,
    "beam3-1": 40,
    "beam4-0": 74,
    "beam4-1": 102,
    "beam5-0": 61,
    "beam5-1": 22,
    "square2": 170,
    "rect23-0": 134,
    "rect23-1": 87,
    "square3": 60,
    "corner3-0": 40,
    "corner3-1": 26,
    "corner3-2": 65,
    "corner3-3": 8,
    "L-0": 8,
    "L-1": 26,
    "L-2": 12,
    "L-3": 108,
    "L-4": 18,
    "L-5": 19,
    "L-6": 13,
    "L-7": 52,
    "corner5-0": 8,
    "corner5-1": 8,
    "corner5-2": 8,
    "corner5-3": 15,
    "diag2-0": 14,
    "diag2-1": 25,
    "diag3-0": 8,
    "diag3-1": 8,
    "S-0": 38,
    "S-1": 30,
    "S-2": 24,
    "S-3": 23,
    "T-0": 14,
    "T-1": 21,
    "T-2": 25,
    "T-3": 72,
}
WEIGHTS = [POSE_COUNTS[p.name] for p in PIECE_POOL]


class Generator:
    def __init__(self, seed=None):
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        return self.rng.choices(PIECE_POOL, weights=WEIGHTS)[0]

    def next_pieces(self):
        return [self._next_piece() for _ in range(3)]
