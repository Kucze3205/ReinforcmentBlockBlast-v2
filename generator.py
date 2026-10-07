"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z trzech pełnych tacek w logach faza0 (10 partii, 1281 klocków).
POSE_COUNTS = {
    "1x1": 47, "beam2-0": 70, "beam2-1": 79, "beam3-0": 62,
    "beam3-1": 38, "beam4-0": 54, "beam4-1": 95, "beam5-0": 33,
    "beam5-1": 21, "square2": 96, "rect23-0": 68, "rect23-1": 45,
    "square3": 37, "corner3-0": 31, "corner3-1": 11, "corner3-2": 14,
    "corner3-3": 6, "L-0": 20, "L-1": 14, "L-2": 16,
    "L-3": 21, "L-4": 10, "L-5": 11, "L-6": 23,
    "L-7": 67, "corner5-0": 10, "corner5-1": 15, "corner5-2": 7,
    "corner5-3": 16, "diag2-0": 13, "diag2-1": 12, "diag3-0": 3,
    "diag3-1": 9, "S-0": 40, "S-1": 21, "S-2": 24,
    "S-3": 17, "T-0": 20, "T-1": 18, "T-2": 22,
    "T-3": 45,
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
