"""
Deterministic Piece Generator

Trzy klocki losowane niezależnie — bez świadomości planszy i bez gwarancji
grywalności tacki. Rozkład doboru zmierzony na oryginale: wagi poz to zliczenia
z logów faza0 (POSE_COUNTS). Dawny model referencji (1/15 na typ, potem 1/n na
orientację) nie pasował: χ² = 729,8 przy df = 40, p = 0.
"""
import random

from pieces import PIECE_POOL

# Pół na pół: pierwsze 48 rund każdej partii (rozkład rośnie z numerem rundy: średni klocek 3.5 -> 5.3 komórki,
# generator jest stacjonarny, więc dopasowany do typowej długości odcinka) i średnia z 10 partii faza0 (po 1/10 na partię, w promilach) z pełnych tacek, bez powtórek po nieudanym ruchu.
# Zliczenia sumowane po partiach dawały przewagę jednej długiej partii (513 z 1548 klocków, większe klocki).
POSE_COUNTS = {
    "1x1": 19.44,
    "beam2-0": 65.07,
    "beam2-1": 77.75,
    "beam3-0": 41.12,
    "beam3-1": 40.25,
    "beam4-0": 34.92,
    "beam4-1": 52.74,
    "beam5-0": 29.64,
    "beam5-1": 35.31,
    "square2": 68.68,
    "rect23-0": 55.71,
    "rect23-1": 42.99,
    "square3": 37.53,
    "corner3-0": 33.45,
    "corner3-1": 14.32,
    "corner3-2": 14.66,
    "corner3-3": 10.3,
    "L-0": 17.88,
    "L-1": 14.03,
    "L-2": 12.83,
    "L-3": 22.85,
    "L-4": 8.44,
    "L-5": 12.2,
    "L-6": 15.85,
    "L-7": 35.61,
    "corner5-0": 7.46,
    "corner5-1": 3.6,
    "corner5-2": 6.49,
    "corner5-3": 7.32,
    "diag2-0": 20.23,
    "diag2-1": 10.05,
    "diag3-0": 6.36,
    "diag3-1": 5.53,
    "S-0": 26.7,
    "S-1": 8.43,
    "S-2": 12.28,
    "S-3": 14.45,
    "T-0": 9.94,
    "T-1": 8.65,
    "T-2": 8.21,
    "T-3": 30.73,
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
