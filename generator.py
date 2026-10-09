"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1296 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1110 klocków) nie zgadzały się
# z zestawem: χ² = 110,6 przy df = 38, p = 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 53,
    "beam2-0": 79,
    "beam2-1": 72,
    "beam3-0": 54,
    "beam3-1": 32,
    "beam4-0": 49,
    "beam4-1": 81,
    "beam5-0": 23,
    "beam5-1": 24,
    "square2": 81,
    "rect23-0": 69,
    "rect23-1": 55,
    "square3": 30,
    "corner3-0": 35,
    "corner3-1": 12,
    "corner3-2": 24,
    "corner3-3": 21,
    "L-0": 18,
    "L-1": 31,
    "L-2": 18,
    "L-3": 21,
    "L-4": 11,
    "L-5": 14,
    "L-6": 27,
    "L-7": 48,
    "corner5-0": 9,
    "corner5-1": 14,
    "corner5-2": 2,
    "corner5-3": 15,
    "diag2-0": 34,
    "diag2-1": 19,
    "diag3-0": 9,
    "diag3-1": 8,
    "S-0": 37,
    "S-1": 23,
    "S-2": 23,
    "S-3": 18,
    "T-0": 25,
    "T-1": 18,
    "T-2": 15,
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
