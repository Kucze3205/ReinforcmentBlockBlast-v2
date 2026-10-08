"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, pierwsze 300 ruchów, 1491 klocków).
POSE_COUNTS = {
    "1x1": 40,
    "beam2-0": 77,
    "beam2-1": 71,
    "beam3-0": 66,
    "beam3-1": 80,
    "beam4-0": 57,
    "beam4-1": 80,
    "beam5-0": 75,
    "beam5-1": 60,
    "square2": 125,
    "rect23-0": 102,
    "rect23-1": 56,
    "square3": 83,
    "corner3-0": 19,
    "corner3-1": 16,
    "corner3-2": 6,
    "corner3-3": 12,
    "L-0": 14,
    "L-1": 24,
    "L-2": 17,
    "L-3": 14,
    "L-4": 6,
    "L-5": 5,
    "L-6": 25,
    "L-7": 67,
    "corner5-0": 6,
    "corner5-1": 12,
    "corner5-2": 4,
    "corner5-3": 11,
    "diag2-0": 15,
    "diag2-1": 10,
    "diag3-0": 24,
    "diag3-1": 1,
    "S-0": 32,
    "S-1": 14,
    "S-2": 34,
    "S-3": 20,
    "T-0": 17,
    "T-1": 24,
    "T-2": 13,
    "T-3": 57,
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
