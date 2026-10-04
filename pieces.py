"""
Block Blast Piece Library

Skalibrowane pod referencję ustaloną w badaniu #2: 15 typów kanonicznych
domkniętych na grupę D4 daje 41 unikalnych orientacji (poz). Gra nie pozwala
obracać klocków, więc każda orientacja jest osobnym klockiem.

UWAGA: zbiór klocków oryginału jest publicznie NIEZMIERZONY (#2, §3.1).
Te 41 poz to najlepsza dostępna rekonstrukcja, nie pomiar — patrz
docs/calibration-assumptions.md, założenie Z-5.
"""

PIECE_GRID = 5  # najdłuższy klocek to belka 1x5


class Piece:
    def __init__(self, shape, name, type_index):
        self.shape = shape
        self.name = name
        self.type_index = type_index
        self.index = None  # ustawiany przy dodaniu do puli


# 15 typów kanonicznych. Orientacje powstają przez domknięcie na D4, nie ręcznie.
CANONICAL_TYPES = [
    ("1x1",      [[1]]),
    ("beam2",    [[1, 1]]),
    ("beam3",    [[1, 1, 1]]),
    ("beam4",    [[1, 1, 1, 1]]),
    ("beam5",    [[1, 1, 1, 1, 1]]),
    ("square2",  [[1, 1], [1, 1]]),
    ("rect23",   [[1, 1, 1], [1, 1, 1]]),
    ("square3",  [[1, 1, 1], [1, 1, 1], [1, 1, 1]]),
    ("corner3",  [[1, 1], [1, 0]]),
    ("L",        [[1, 0], [1, 0], [1, 1]]),
    ("corner5",  [[1, 0, 0], [1, 0, 0], [1, 1, 1]]),
    ("diag2",    [[1, 0], [0, 1]]),
    ("diag3",    [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
    ("S",        [[0, 1, 1], [1, 1, 0]]),
    ("T",        [[1, 1, 1], [0, 1, 0]]),
]

EXPECTED_POSES = 41


def _rotate(shape):
    """Obrót o 90 stopni w prawo."""
    return [list(row) for row in zip(*shape[::-1])]


def _mirror(shape):
    return [row[::-1] for row in shape]


def _d4_closure(shape):
    """Wszystkie orientacje kształtu pod grupą D4, bez duplikatów, w stabilnej kolejności."""
    seen = []
    current = shape
    for _ in range(4):
        for variant in (current, _mirror(current)):
            key = tuple(tuple(row) for row in variant)
            if key not in [tuple(tuple(r) for r in s) for s in seen]:
                seen.append([list(row) for row in variant])
        current = _rotate(current)
    return seen


PIECE_POOL = []
PIECE_TYPES = []  # PIECE_TYPES[t] = lista indeksów poz należących do typu t

for type_index, (type_name, base_shape) in enumerate(CANONICAL_TYPES):
    poses = _d4_closure(base_shape)
    pose_indices = []
    for orientation, shape in enumerate(poses):
        name = type_name if len(poses) == 1 else f"{type_name}-{orientation}"
        piece = Piece(shape, name, type_index)
        piece.index = len(PIECE_POOL)
        PIECE_POOL.append(piece)
        pose_indices.append(piece.index)
    PIECE_TYPES.append(pose_indices)

# Asercja z referencji (bbengine/src/tables.h): dedup musi dać dokładnie 41 poz.
assert len(PIECE_POOL) == EXPECTED_POSES, (
    f"Domknięcie D4 dało {len(PIECE_POOL)} poz zamiast {EXPECTED_POSES}"
)


def pad_to_grid(shape, size=PIECE_GRID):
    """Wkłada kształt w lewy górny róg kwadratu size x size."""
    grid = [[0] * size for _ in range(size)]
    for r, row in enumerate(shape):
        for c, cell in enumerate(row):
            grid[r][c] = cell
    return grid


PIECE_SHAPES = [(p.shape, p.name) for p in PIECE_POOL]
PIECE_SHAPES_PADDED = [(pad_to_grid(p.shape), p.name) for p in PIECE_POOL]
