"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1221 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1080 klocków) pochodziły z innego zestawu:
# χ² = 141,8 przy df = 37, p = 0. diag3-1 nie wystąpiło w zestawie, waga 1 zamiast 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 27,
    "beam2-0": 71,
    "beam2-1": 60,
    "beam3-0": 51,
    "beam3-1": 44,
    "beam4-0": 47,
    "beam4-1": 83,
    "beam5-0": 33,
    "beam5-1": 35,
    "square2": 104,
    "rect23-0": 87,
    "rect23-1": 57,
    "square3": 70,
    "corner3-0": 32,
    "corner3-1": 12,
    "corner3-2": 12,
    "corner3-3": 11,
    "L-0": 12,
    "L-1": 17,
    "L-2": 7,
    "L-3": 15,
    "L-4": 15,
    "L-5": 8,
    "L-6": 35,
    "L-7": 43,
    "corner5-0": 10,
    "corner5-1": 15,
    "corner5-2": 10,
    "corner5-3": 11,
    "diag2-0": 13,
    "diag2-1": 9,
    "diag3-0": 10,
    "diag3-1": 1,
    "S-0": 20,
    "S-1": 23,
    "S-2": 5,
    "S-3": 24,
    "T-0": 18,
    "T-1": 14,
    "T-2": 9,
    "T-3": 42,
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
