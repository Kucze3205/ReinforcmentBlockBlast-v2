"""
Block Blast Human-Playable UI (pygame)
"""
import pygame
import sys

from board import Board

CELL_SIZE = 60
GRID_SIZE = 8
MARGIN = 28
# Ensure enough width for 3 large pieces in the panel
PIECE_PANEL_HEIGHT = 180
SCREEN_WIDTH = max(GRID_SIZE * CELL_SIZE + 2 * MARGIN, 3 * CELL_SIZE * 5 + 2 * MARGIN)
SCREEN_HEIGHT = GRID_SIZE * CELL_SIZE + PIECE_PANEL_HEIGHT + 3 * MARGIN + 80

COLORS = {
    'bg': (30, 30, 40),
    'grid': (60, 60, 80),
    'block': (120, 180, 240),
    'piece': (200, 120, 120),
    'preview': (200, 200, 200, 120),
    'invalid': (220, 60, 60, 120),
    'score': (255, 255, 255),
    'streak': (255, 220, 120),
}

class UI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.NOFRAME)
        pygame.display.set_caption("Block Blast")
        self.font = pygame.font.SysFont(None, 32)
        self.clock = pygame.time.Clock()
        # Button definitions
        self.button_height = 50
        self.button_width = 180
        self.button_margin = 20
        # Place buttons below the piece panel
        button_y = SCREEN_HEIGHT - self.button_height - self.button_margin // 2
        self.buttons = {
            'train': pygame.Rect(MARGIN, button_y, self.button_width, self.button_height),
            'step': pygame.Rect(MARGIN + self.button_width + self.button_margin, button_y, self.button_width, self.button_height),
            'restart': pygame.Rect(MARGIN + 2 * (self.button_width + self.button_margin), button_y, self.button_width, self.button_height)
        }
        self.training = False
        

    def draw_grid(self, board):
        for y in range(GRID_SIZE):
            for x in range(GRID_SIZE):
                rect = pygame.Rect(MARGIN + x * CELL_SIZE, MARGIN + y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
                pygame.draw.rect(self.screen, COLORS['grid'], rect, 1)
                if board[y][x]:
                    pygame.draw.rect(self.screen, COLORS['block'], rect.inflate(-6, -6))

    def draw_piece(self, piece, x, y, alpha=255, invalid=False):
        for dy, row in enumerate(piece.shape):
            for dx, cell in enumerate(row):
                if cell:
                    px = x + dx * CELL_SIZE
                    py = y + dy * CELL_SIZE
                    rect = pygame.Rect(px, py, CELL_SIZE, CELL_SIZE)
                    color = COLORS['invalid'] if invalid else COLORS['piece']
                    surf = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                    surf.fill((*color[:3], alpha))
                    self.screen.blit(surf, rect)

    def draw_panel(self, pieces):
        for idx, piece in enumerate(pieces):
            if piece is None:
                continue
            px = MARGIN + idx * (CELL_SIZE * 5)
            py = SCREEN_HEIGHT - PIECE_PANEL_HEIGHT + MARGIN
            self.draw_piece(piece, px, py)

    def draw_info(self, score, streak, round_num):
        score_text = self.font.render(f"Score: {score}", True, COLORS['score'])
        streak_text = self.font.render(f"Streak: {streak}", True, COLORS['streak'])
        round_text = self.font.render(f"Round: {round_num}/3", True, COLORS['score'])
        self.screen.blit(score_text, (MARGIN, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))
        self.screen.blit(streak_text, (MARGIN + 180, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))
        self.screen.blit(round_text, (MARGIN + 360, SCREEN_HEIGHT - PIECE_PANEL_HEIGHT - 2 * MARGIN))

    def draw_buttons(self):
        # Button styles
        button_styles = {
            'train': ((70, 180, 70), "Stop Training" if self.training else "Start Training"),
            'step': ((70, 70, 180), "Step"),
            'restart': ((180, 70, 70), "Restart")
        }
        for name, rect in self.buttons.items():
            color, label = button_styles[name]
            # Draw filled rectangle
            pygame.draw.rect(self.screen, color, rect, border_radius=8)
            # Draw border
            pygame.draw.rect(self.screen, (255,255,255), rect, 2, border_radius=8)
            # Render text
            text = self.font.render(label, True, (255,255,255))
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)

    def check_button_click(self, pos):
        for name, rect in self.buttons.items():
            if rect.collidepoint(pos):
                return name
        return None

    def set_training(self, training):
        self.training = training

