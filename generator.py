"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków ze wszystkich pełnych tacek (3 klocki) zestawu kontrolnego faza0:
# 10 partii, 365 tacek, 1095 klocków. Poprzednie wagi (1491 klocków z "pierwszych 300 ruchów")
# liczyły te same tacki wielokrotnie, więc rozkład był zniekształcony: χ² = 254 przy p = 0.
POSE_COUNTS = {
    "1x1": 28,
    "beam2-0": 66,
    "beam2-1": 59,
    "beam3-0": 64,
    "beam3-1": 47,
    "beam4-0": 45,
    "beam4-1": 69,
    "beam5-0": 35,
    "beam5-1": 26,
    "square2": 72,
    "rect23-0": 25,
    "rect23-1": 37,
    "square3": 51,
    "corner3-0": 18,
    "corner3-1": 11,
    "corner3-2": 16,
    "corner3-3": 19,
    "L-0": 28,
    "L-1": 18,
    "L-2": 6,
    "L-3": 18,
    "L-4": 16,
    "L-5": 13,
    "L-6": 28,
    "L-7": 54,
    "corner5-0": 5,
    "corner5-1": 8,
    "corner5-2": 7,
    "corner5-3": 14,
    "diag2-0": 22,
    "diag2-1": 7,
    "diag3-0": 5,
    "diag3-1": 3,
    "S-0": 24,
    "S-1": 10,
    "S-2": 25,
    "S-3": 10,
    "T-0": 13,
    "T-1": 11,
    "T-2": 15,
    "T-3": 47,
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
