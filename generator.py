"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z pełnych tacek (3 klocki) w logach faza0 (10 partii, 1011 klocków).
POSE_COUNTS = {
    "1x1": 22, "beam2-0": 60, "beam2-1": 75, "beam3-0": 51, "beam3-1": 34,
    "beam4-0": 40, "beam4-1": 68, "beam5-0": 28, "beam5-1": 26, "square2": 62,
    "rect23-0": 36, "rect23-1": 49, "square3": 23, "corner3-0": 33,
    "corner3-1": 15, "corner3-2": 8, "corner3-3": 9, "L-0": 8, "L-1": 14,
    "L-2": 18, "L-3": 11, "L-4": 7, "L-5": 5, "L-6": 26, "L-7": 54,
    "corner5-0": 6, "corner5-1": 12, "corner5-2": 3, "corner5-3": 15,
    "diag2-0": 20, "diag2-1": 20, "diag3-0": 11, "diag3-1": 7, "S-0": 25,
    "S-1": 11, "S-2": 18, "S-3": 10, "T-0": 5, "T-1": 16, "T-2": 5, "T-3": 45,
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
