"""
Deterministic Piece Generator

Losuje jak referencja z badania #2 (bbengine/src/env.h): najpierw 1/15 na typ
kanoniczny, POTEM 1/n na orientację w obrębie typu (R-8). Trzy klocki losowane
niezależnie — bez świadomości planszy i bez gwarancji grywalności tacki.

Rozkład doboru w oryginale jest publicznie niezmierzony; to założenie modelowe
autora referencji, nie pomiar — patrz docs/calibration-assumptions.md (Z-6).
"""
import random

from pieces import PIECE_POOL, PIECE_TYPES


class Generator:
    def __init__(self, seed=None):
        self.reset(seed)

    def reset(self, seed=None):
        self.seed = seed
        # R-9: seed był zapisywany, ale nigdy nieużyty. Bez tego benchmark na
        # ustalonych seedach jest niewykonalny.
        self.rng = random.Random(seed)

    def _next_piece(self):
        pose_indices = self.rng.choice(PIECE_TYPES)
        return PIECE_POOL[self.rng.choice(pose_indices)]

    def next_pieces(self):
        return [self._next_piece() for _ in range(3)]
