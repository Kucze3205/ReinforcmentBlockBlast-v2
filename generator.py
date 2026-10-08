"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z pełnych tacek (3 klocki) w logach faza0 (10 partii, 1407 klocków).
POSE_COUNTS = {
    "1x1": 49, "beam2-0": 86, "beam2-1": 92, "beam3-0": 51, "beam3-1": 40,
    "beam4-0": 48, "beam4-1": 105, "beam5-0": 32, "beam5-1": 23,
    "square2": 107, "rect23-0": 53, "rect23-1": 58, "square3": 34,
    "corner3-0": 28, "corner3-1": 14, "corner3-2": 17, "corner3-3": 14,
    "L-0": 6, "L-1": 33, "L-2": 14, "L-3": 18, "L-4": 15, "L-5": 15,
    "L-6": 28, "L-7": 93, "corner5-0": 12, "corner5-1": 7, "corner5-2": 5,
    "corner5-3": 12, "diag2-0": 16, "diag2-1": 30, "diag3-0": 12,
    "diag3-1": 4, "S-0": 51, "S-1": 20, "S-2": 23, "S-3": 17, "T-0": 19,
    "T-1": 31, "T-2": 16, "T-3": 59,
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
