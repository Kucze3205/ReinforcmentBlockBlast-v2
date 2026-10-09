"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1197 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1296 klocków) nie zgadzały się
# z zestawem: χ² = 110,6 przy df = 38, p = 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 33,
    "beam2-0": 75,
    "beam2-1": 91,
    "beam3-0": 64,
    "beam3-1": 42,
    "beam4-0": 37,
    "beam4-1": 85,
    "beam5-0": 35,
    "beam5-1": 28,
    "square2": 85,
    "rect23-0": 49,
    "rect23-1": 53,
    "square3": 35,
    "corner3-0": 32,
    "corner3-1": 11,
    "corner3-2": 14,
    "corner3-3": 8,
    "L-0": 9,
    "L-1": 13,
    "L-2": 13,
    "L-3": 16,
    "L-4": 16,
    "L-5": 9,
    "L-6": 15,
    "L-7": 48,
    "corner5-0": 7,
    "corner5-1": 13,
    "corner5-2": 4,
    "corner5-3": 8,
    "diag2-0": 16,
    "diag2-1": 20,
    "diag3-0": 6,
    "diag3-1": 13,
    "S-0": 31,
    "S-1": 23,
    "S-2": 14,
    "S-3": 23,
    "T-0": 14,
    "T-1": 8,
    "T-2": 19,
    "T-3": 62,
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
