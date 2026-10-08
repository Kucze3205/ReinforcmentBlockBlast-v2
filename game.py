"""
Block Blast Game Engine

Skalibrowany pod wzór referencyjny z badania #2. Punktacja jest naliczana
po KAŻDYM postawieniu (R-3), combo mnoży bonus za czyszczenie (R-2) i wygasa
przez licznik, a nie natychmiast (R-4). `score` kumuluje się przez całą partię.
"""
from board import Board
from generator import Generator
from scoring import (
    COMBO_COUNTER_BASE,
    FULL_CLEAR_BONUS,
    FULL_CLEAR_MIN_COMBO,
    clear_points,
    placement_points,
)


class Game:
    def __init__(self, seed=None):
        self.board = Board()
        self.generator = Generator(seed)
        self.reset(seed)

    def reset(self, seed=None):
        self.generator.reset(seed)
        self.board.reset()
        self.score = 0
        self.combo = 0
        self.combo_counter = COMBO_COUNTER_BASE
        self.round_placement = 0
        self.placements = 0          # przeżycie: liczba udanych postawień w partii
        self.last_lines_cleared = 0  # linie wyczyszczone ostatnim postawieniem
        self.pieces = self.generator.next_pieces()
        self.done = False

    def available_actions(self):
        actions = []
        for idx, piece in enumerate(self.pieces):
            if piece is None:
                continue
            for y in range(Board.HEIGHT - len(piece.shape) + 1):
                for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                    if self.board.can_place_piece(piece, x, y):
                        actions.append((idx, x, y))
        return actions

    def step(self, action):
        idx, x, y = action
        piece = self.pieces[idx] if 0 <= idx < len(self.pieces) else None
        if piece is None or not self.board.place_piece(piece, x, y):
            self.done = True
            return -5, self.score, self.done, "wrong_placement"

        gained = self.apply_placement(idx)
        self.placements += 1

        if not self._can_place_any():
            self.done = True
            return -5, self.score, True, "game_over"

        return gained, self.score, self.done, "successful placement"

    def apply_placement(self, idx):
        """Nalicza punkty za jedno postawienie i zwraca przyrost. Klocek jest już na planszy."""
        gained = placement_points(self.pieces[idx])

        rows, cols = self.board.check_full_lines()
        lines = len(rows) + len(cols)
        self.last_lines_cleared = lines

        # Klocek znika z tacki przed aktualizacją combo: licznik wygaśnięcia
        # zależy od tego, ile klocków zostało w tacce (referencja: 3 + 0/1/2).
        self.pieces[idx] = None
        self.round_placement += 1
        remaining = sum(1 for p in self.pieces if p is not None)

        if lines > 0:
            # zmierzone: w trwającym streaku combo rośnie o liczbę linii, ale pierwsze czyszczenie
            # po resecie daje combo=1 niezależnie od liczby linii (bonus B(l) już ją zawiera)
            # zmierzone: czyszczenie 3 kolumn bez wierszy podnosi combo tylko o 1 (faza0-1 n77, faza0-3 n41,
            # faza0-6 n179: 20->21, 20->21, 29->30), 3 wiersze albo mieszane o 3
            gain = 1 if len(cols) >= 3 and not rows else lines
            self.combo = 1 if self.combo == 0 else self.combo + gain
            self.combo_counter = COMBO_COUNTER_BASE + remaining
            gained += clear_points(self.combo, lines)
        elif self.combo_counter <= 1:
            self.combo = 0
            self.combo_counter = COMBO_COUNTER_BASE
        else:
            self.combo_counter -= 1

        self.board.clear_lines(rows, cols)

        # zmierzone: apka nie daje bonusu przy combo <= 5 (faza0-10 n2, faza0-5 n10, odcinek n5: combo 2, 5, 2),
        # daje przy combo >= 7 (faza0-6 n15, faza0-4 n24, faza0-10 n61 i n64)
        if self.combo >= FULL_CLEAR_MIN_COMBO and not any(any(row) for row in self.board.grid):
            gained += FULL_CLEAR_BONUS

        if self.round_placement == 3:
            self.pieces = self.generator.next_pieces()
            self.round_placement = 0

        self.score += gained
        return gained

    def _can_place_any(self):
        for piece in self.pieces:
            if piece is None:
                continue
            for y in range(Board.HEIGHT - len(piece.shape) + 1):
                for x in range(Board.WIDTH - len(piece.shape[0]) + 1):
                    if self.board.can_place_piece(piece, x, y):
                        return True
        return False

    def get_state(self):
        return {
            "board": [row[:] for row in self.board.grid],
            "pieces": list(self.pieces),
            "score": self.score,
            "combo": self.combo,
            "placement_in_round": self.round_placement + 1,
        }
