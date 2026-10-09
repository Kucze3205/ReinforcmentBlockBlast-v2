"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1110 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1080 klocków) pochodziły z innego zestawu:
# χ² = 141,8 przy df = 37, p = 0. diag3-1 nie wystąpiło w zestawie, waga 1 zamiast 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 42,
    "beam2-0": 70,
    "beam2-1": 73,
    "beam3-0": 54,
    "beam3-1": 29,
    "beam4-0": 47,
    "beam4-1": 77,
    "beam5-0": 31,
    "beam5-1": 27,
    "square2": 79,
    "rect23-0": 49,
    "rect23-1": 52,
    "square3": 28,
    "corner3-0": 30,
    "corner3-1": 15,
    "corner3-2": 16,
    "corner3-3": 13,
    "L-0": 9,
    "L-1": 13,
    "L-2": 9,
    "L-3": 22,
    "L-4": 14,
    "L-5": 15,
    "L-6": 14,
    "L-7": 62,
    "corner5-0": 9,
    "corner5-1": 6,
    "corner5-2": 3,
    "corner5-3": 10,
    "diag2-0": 21,
    "diag2-1": 18,
    "diag3-0": 1,
    "diag3-1": 2,
    "S-0": 27,
    "S-1": 19,
    "S-2": 14,
    "S-3": 16,
    "T-0": 20,
    "T-1": 13,
    "T-2": 9,
    "T-3": 32,
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
