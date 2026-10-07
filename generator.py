"""
Deterministic Piece Generator

Rozkład poz zmierzony na logach mostu faza0 (462 klocków z tacek, 10 partii):
oryginał nie losuje równo po typach (jak zakładała referencja #2, R-8), tylko
bardzo nierówno po pozach — belki i kwadraty wypadają kilkukrotnie częściej niż
S, T czy diag3. Wagi = liczność poz w logach + 1 (wygładzenie). Trzy klocki losowane
niezależnie, bez świadomości planszy.
"""
import random

from pieces import PIECE_POOL

# Liczności poz (kolejność PIECE_POOL) z tacek w logach faza0.
POSE_COUNTS = [
    12, 29, 24, 28, 13, 7, 32, 28, 11, 37,
    28, 19, 14, 12, 9, 4, 3, 2, 10, 7,
    10, 2, 4, 9, 13, 3, 7, 3, 10, 4,
    14, 3, 2, 11, 3, 4, 7, 1, 2, 4,
    17,
]
POSE_WEIGHTS = [c + 1 for c in POSE_COUNTS]


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
