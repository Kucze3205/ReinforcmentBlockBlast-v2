"""
Block Blast Board Logic
"""

class Board:
    WIDTH = 8
    HEIGHT = 8

    def __init__(self):
        self.grid = [[0 for _ in range(Board.WIDTH)] for _ in range(Board.HEIGHT)]

    def reset(self):
        self.grid = [[0 for _ in range(Board.WIDTH)] for _ in range(Board.HEIGHT)]

    def place_piece(self, piece, x, y):
        if piece is None:
            return False
        if not self.can_place_piece(piece, x, y):
            return False
        
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    self.grid[y + dy][x + dx] = 1
        return True
    
    def can_place_piece(self, piece, x, y):
        if piece is None:
            return False
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    bx, by = x + dx, y + dy
                    if not (0 <= bx < Board.WIDTH and 0 <= by < Board.HEIGHT):
                        return False
                    if self.grid[by][bx]:
                        return False
        return True

    def check_full_lines(self):
        full_rows = [i for i, row in enumerate(self.grid) if all(row)]
        full_cols = [j for j in range(Board.WIDTH) if all(self.grid[i][j] for i in range(Board.HEIGHT))]
        return full_rows, full_cols

    def clear_lines(self, rows, cols):
        for r in rows:
            self.grid[r] = [0] * Board.WIDTH
        for c in cols:
            for r in range(Board.HEIGHT):
                self.grid[r][c] = 0

    def copy(self):
        new_board = Board()
        new_board.grid = [row[:] for row in self.grid]
        return new_board
