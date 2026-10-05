"""
Deterministic Piece Generator

Pozę losuje z wag dopasowanych do tacek z logów mostu (wcześniej: 1/15 na typ, potem
1/n na orientację — test χ² na logach dawał p=0). Trzy klocki losowane niezależnie —
bez świadomości planszy i bez gwarancji grywalności tacki.
"""
import random

from pieces import PIECE_POOL

# Tacki z logów mostu (faza0, 10 partii, 811 klocków): ile razy wypadła dana poza.
# Rozkład oryginału nie jest ani równy na typ, ani na pozę (np. beam4-1 60 vs beam4-0 25,
# L-7 28 vs L-0 5), więc waga to zmierzona liczność + 1 (wygładzenie rzadkich póz).
OBSERVED_COUNTS = {
    "1x1": 25, "beam2-0": 45, "beam2-1": 41, "beam3-0": 24, "beam3-1": 39,
    "beam4-0": 25, "beam4-1": 60, "beam5-0": 23, "beam5-1": 18, "square2": 66,
    "rect23-0": 37, "rect23-1": 50, "square3": 24,
    "corner3-0": 34, "corner3-1": 9, "corner3-2": 13, "corner3-3": 13,
    "L-0": 5, "L-1": 17, "L-2": 17, "L-3": 8, "L-4": 10, "L-5": 7, "L-6": 10, "L-7": 28,
    "corner5-0": 9, "corner5-1": 1, "corner5-2": 3, "corner5-3": 9,
    "diag2-0": 6, "diag2-1": 12, "diag3-0": 5, "diag3-1": 9,
    "S-0": 15, "S-1": 9, "S-2": 14, "S-3": 11,
    "T-0": 16, "T-1": 10, "T-2": 11, "T-3": 23,
}
POSE_WEIGHTS = [OBSERVED_COUNTS[p.name] + 1 for p in PIECE_POOL]


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
