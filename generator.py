"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1371 klocków) liczone tak jak miara χ² w ocenie
# (pierwsza pełna tacka rundy, inna niż poprzednia). Poprzednie wagi (1200 klocków) były z innego zliczenia
# i nie zgadzały się z zestawem: χ² = 169,5 przy df = 39, p = 0. Generator bez planszy odtwarza
# tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 41,
    "beam2-0": 61,
    "beam2-1": 83,
    "beam3-0": 71,
    "beam3-1": 50,
    "beam4-0": 43,
    "beam4-1": 95,
    "beam5-0": 41,
    "beam5-1": 36,
    "square2": 79,
    "rect23-0": 70,
    "rect23-1": 62,
    "square3": 53,
    "corner3-0": 34,
    "corner3-1": 32,
    "corner3-2": 29,
    "corner3-3": 17,
    "L-0": 17,
    "L-1": 21,
    "L-2": 22,
    "L-3": 23,
    "L-4": 10,
    "L-5": 14,
    "L-6": 23,
    "L-7": 43,
    "corner5-0": 8,
    "corner5-1": 14,
    "corner5-2": 10,
    "corner5-3": 16,
    "diag2-0": 25,
    "diag2-1": 20,
    "diag3-0": 12,
    "diag3-1": 5,
    "S-0": 39,
    "S-1": 19,
    "S-2": 23,
    "S-3": 19,
    "T-0": 20,
    "T-1": 18,
    "T-2": 16,
    "T-3": 37,
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
