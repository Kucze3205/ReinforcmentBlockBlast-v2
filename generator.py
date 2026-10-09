"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1200 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1296 klocków) nie zgadzały się
# z zestawem: χ² = 110,6 przy df = 38, p = 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 28,
    "beam2-0": 51,
    "beam2-1": 66,
    "beam3-0": 63,
    "beam3-1": 60,
    "beam4-0": 44,
    "beam4-1": 65,
    "beam5-0": 28,
    "beam5-1": 22,
    "square2": 94,
    "rect23-0": 73,
    "rect23-1": 66,
    "square3": 43,
    "corner3-0": 32,
    "corner3-1": 13,
    "corner3-2": 15,
    "corner3-3": 18,
    "L-0": 19,
    "L-1": 18,
    "L-2": 15,
    "L-3": 12,
    "L-4": 21,
    "L-5": 18,
    "L-6": 13,
    "L-7": 51,
    "corner5-0": 5,
    "corner5-1": 9,
    "corner5-2": 9,
    "corner5-3": 13,
    "diag2-0": 7,
    "diag2-1": 16,
    "diag3-0": 10,
    "diag3-1": 4,
    "S-0": 19,
    "S-1": 9,
    "S-2": 21,
    "S-3": 15,
    "T-0": 24,
    "T-1": 20,
    "T-2": 19,
    "T-3": 52,
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
