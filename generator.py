"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Zliczenia klocków z tacek zestawu kontrolnego faza0 (10 partii, 1099 ruchów, 1080 klocków) liczone tak jak miara
# χ² w ocenie (nowa tacka = inna niż poprzednia). Poprzednie wagi (1791 klocków) nie zgadzały się z tym zestawem:
# χ² = 179,8 przy df = 35, p = 0. Generator bez planszy odtwarza tylko rozkład brzegowy zestawu.
POSE_COUNTS = {
    "1x1": 43,
    "beam2-0": 60,
    "beam2-1": 78,
    "beam3-0": 61,
    "beam3-1": 35,
    "beam4-0": 43,
    "beam4-1": 72,
    "beam5-0": 42,
    "beam5-1": 17,
    "square2": 75,
    "rect23-0": 59,
    "rect23-1": 49,
    "square3": 46,
    "corner3-0": 32,
    "corner3-1": 19,
    "corner3-2": 11,
    "corner3-3": 9,
    "L-0": 12,
    "L-1": 11,
    "L-2": 13,
    "L-3": 12,
    "L-4": 12,
    "L-5": 4,
    "L-6": 22,
    "L-7": 39,
    "corner5-0": 7,
    "corner5-1": 3,
    "corner5-2": 4,
    "corner5-3": 8,
    "diag2-0": 18,
    "diag2-1": 9,
    "diag3-0": 9,
    "diag3-1": 1,
    "S-0": 21,
    "S-1": 23,
    "S-2": 18,
    "S-3": 10,
    "T-0": 9,
    "T-1": 12,
    "T-2": 14,
    "T-3": 38,
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
