"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki.

Rozkład doboru: pomiar z tacek mostu (10 partii, 867 klocków, .zadanie/dane).
Założenie z badania #2 (1/15 na typ, potem 1/n na orientację) nie zgadzało się
z oryginałem (χ² 398 przy df=40): oryginał daje krótkie belki, kwadraty i prostokąty
częściej niż diagonale i rogi, a orientacje jednego typu nie są równe. Wagi poz to
zliczenia z logów + 2 (wygładzanie), w kolejności PIECE_POOL.
"""
import random

from pieces import PIECE_POOL

POSE_COUNTS = [
    25, 48, 40, 47, 30, 32, 66, 33, 29, 52, 43, 48, 33, 24, 11, 4, 5, 2, 11, 11, 14,
    16, 13, 9, 34, 2, 6, 10, 12, 7, 1, 14, 4, 10, 15, 18, 11, 12, 16, 16, 33,
]
POSE_WEIGHTS = [c + 2 for c in POSE_COUNTS]
assert len(POSE_WEIGHTS) == len(PIECE_POOL)


class Generator:
    def __init__(self, seed=None):
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        return self.rng.choices(PIECE_POOL, weights=POSE_WEIGHTS)[0]

    def next_pieces(self):
        return [self._next_piece() for _ in range(3)]
