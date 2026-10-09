"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1347 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1371 klocków) nie zgadzały się z tym
# zliczeniem: χ² = 134,4 przy df = 39, p = 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 60,
    "beam2-0": 94,
    "beam2-1": 97,
    "beam3-0": 67,
    "beam3-1": 25,
    "beam4-0": 39,
    "beam4-1": 96,
    "beam5-0": 27,
    "beam5-1": 21,
    "square2": 105,
    "rect23-0": 69,
    "rect23-1": 53,
    "square3": 26,
    "corner3-0": 36,
    "corner3-1": 19,
    "corner3-2": 26,
    "corner3-3": 13,
    "L-0": 14,
    "L-1": 15,
    "L-2": 14,
    "L-3": 28,
    "L-4": 17,
    "L-5": 22,
    "L-6": 12,
    "L-7": 50,
    "corner5-0": 6,
    "corner5-1": 7,
    "corner5-2": 7,
    "corner5-3": 23,
    "diag2-0": 20,
    "diag2-1": 13,
    "diag3-0": 12,
    "diag3-1": 14,
    "S-0": 35,
    "S-1": 13,
    "S-2": 25,
    "S-3": 18,
    "T-0": 20,
    "T-1": 18,
    "T-2": 20,
    "T-3": 51,
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
