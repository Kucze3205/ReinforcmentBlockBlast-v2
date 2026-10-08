"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z pełnych tacek (3 klocki) w logach faza0 (10 partii, 1245 klocków).
POSE_COUNTS = {
    "1x1": 43,
    "beam2-0": 62,
    "beam2-1": 63,
    "beam3-0": 73,
    "beam3-1": 43,
    "beam4-0": 48,
    "beam4-1": 104,
    "beam5-0": 35,
    "beam5-1": 21,
    "square2": 82,
    "rect23-0": 75,
    "rect23-1": 79,
    "square3": 42,
    "corner3-0": 22,
    "corner3-1": 13,
    "corner3-2": 8,
    "corner3-3": 10,
    "L-0": 8,
    "L-1": 22,
    "L-2": 8,
    "L-3": 24,
    "L-4": 4,
    "L-5": 10,
    "L-6": 37,
    "L-7": 59,
    "corner5-0": 7,
    "corner5-1": 6,
    "corner5-2": 10,
    "corner5-3": 11,
    "diag2-0": 15,
    "diag2-1": 11,
    "diag3-0": 13,
    "diag3-1": 7,
    "S-0": 37,
    "S-1": 7,
    "S-2": 13,
    "S-3": 17,
    "T-0": 8,
    "T-1": 25,
    "T-2": 17,
    "T-3": 46,
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
