"""
Block Blast Engine Test Suite

Testy pilnują kalibracji pod wzór referencyjny z badania #2. Każdy test, który
sprawdza liczbę, jest przywiązany do konkretnej rozbieżności (R-1..R-10), żeby
regresja wskazywała, co dokładnie się rozjechało.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game import Game
from generator import Generator
from pieces import CANONICAL_TYPES, EXPECTED_POSES, PIECE_POOL, PIECE_TYPES
from scoring import FULL_CLEAR_BONUS, clear_points, line_bonus, placement_points

ONE_BY_ONE = PIECE_POOL[0]


def row_full_except(game, x, filler=False):
    """Plansza z wierszem 0 pełnym poza kolumną x — jedno postawienie czyści jedną linię.

    `filler` zostawia komórkę poza wierszem 0, żeby plansza nie zrobiła się pusta
    i nie doliczył się bonus za pełne czyszczenie (osobny test).
    """
    game.board.grid = [[0] * 8 for _ in range(8)]
    for col in range(8):
        game.board.grid[0][col] = 1
    game.board.grid[0][x] = 0
    if filler:
        game.board.grid[7][0] = 1


def place_1x1(game, x, y):
    game.pieces = [ONE_BY_ONE, None, None]
    game.round_placement = 2  # kolejne postawienie domyka tackę
    game.board.place_piece(ONE_BY_ONE, x, y)
    return game.apply_placement(0)


class TestScoringFormula(unittest.TestCase):
    """R-1: bonus bazowy to 10*l*(l-1), a nie 10*k^2."""

    def test_placement_points_are_cell_count(self):
        for piece in PIECE_POOL:
            cells = sum(sum(row) for row in piece.shape)
            self.assertEqual(placement_points(piece), cells)

    def test_line_bonus_matches_reference(self):
        self.assertEqual(line_bonus(0), 0)
        self.assertEqual(line_bonus(1), 10)
        self.assertEqual(line_bonus(2), 20)
        self.assertEqual(line_bonus(3), 60)

    def test_five_and_six_lines_give_the_two_repeated_numbers(self):
        # 200 i 300 to jedyne dwie liczby, które poradniki powtarzają niezależnie.
        self.assertEqual(line_bonus(5), 200)
        self.assertEqual(line_bonus(6), 300)

    def test_combo_multiplies_the_bonus(self):
        # R-2: combo jest mnożnikiem całego bonusu, nie dodatkiem.
        self.assertEqual(clear_points(1, 2), 20)
        self.assertEqual(clear_points(3, 2), 60)
        self.assertEqual(clear_points(0, 2), 0)


class TestMeasuredComboLadder(unittest.TestCase):
    """Wartości z logów faza0: partia 5 n62 (300), n66 (520), n70 (2040); partia 1 n38 (380)."""

    def test_bonus_unit_grows_with_combo(self):
        self.assertEqual(clear_points(5, 1), 50)
        self.assertEqual(clear_points(6, 1), 90)
        self.assertEqual(clear_points(10, 2), 300)
        self.assertEqual(clear_points(11, 1), 220)
        self.assertEqual(clear_points(13, 2), 520)
        self.assertEqual(clear_points(17, 3), 2040)

    def test_bonus_decays_with_game_score(self):
        # faza0, ruch po ruchu: bonus spada do 80/60/40/30% od 6077/6607/7203/8409 pkt w każdej partii, niezależnie od
        # tempa punktów (partie 3 i 5 mają 30% przy ~10 tys. pkt; wcześniej testy opisywały błędny "zatrzask tempa").
        self.assertEqual(clear_points(23, 1, 5599), 460)
        self.assertEqual(clear_points(9, 1, 6206), 108)
        self.assertEqual(clear_points(12, 1, 6638), 144)
        self.assertEqual(clear_points(16, 1, 7313), 128)
        self.assertEqual(clear_points(23, 1, 8437), 138)
        self.assertEqual(clear_points(37, 1, 17652), 222)
        self.assertEqual(clear_points(12, 1), 240)

    def test_combo_grows_by_lines_cleared(self):
        game = Game(seed=1)
        game.board.grid = [[1] * 8 for _ in range(2)] + [[0] * 8 for _ in range(6)]
        game.board.grid[0][0] = game.board.grid[1][0] = 0
        game.pieces = [p for p in PIECE_POOL if p.name == "beam2-1"][:1] + [None, None]
        game.round_placement = 2
        game.board.place_piece(game.pieces[0], 0, 0)
        game.apply_placement(0)
        # pierwsze czyszczenie po resecie daje combo=1, niezależnie od liczby linii
        self.assertEqual(game.combo, 1)

    def test_combo_grows_by_lines_cleared_in_streak(self):
        game = Game(seed=1)
        game.combo = 3
        game.board.grid = [[1] * 8 for _ in range(2)] + [[0] * 8 for _ in range(6)]
        game.board.grid[0][0] = game.board.grid[1][0] = 0
        game.pieces = [p for p in PIECE_POOL if p.name == "beam2-1"][:1] + [None, None]
        game.round_placement = 2
        game.board.place_piece(game.pieces[0], 0, 0)
        game.apply_placement(0)
        self.assertEqual(game.combo, 5)

    def test_three_columns_raise_combo_by_one(self):
        # zmierzone w faza0: 3 kolumny bez wierszy dają +1 (20->21), nie +3
        game = Game(seed=1)
        game.combo = 20
        game.board.grid = [[0] * 8] + [[1, 1, 1, 0, 0, 0, 0, 0] for _ in range(7)]
        piece = [p for p in PIECE_POOL if p.name == "beam3-0"][0]
        game.pieces = [piece, None, None]
        game.round_placement = 2
        game.board.place_piece(piece, 0, 0)
        game.apply_placement(0)
        self.assertEqual(game.last_lines_cleared, 3)
        self.assertEqual(game.combo, 21)


class TestComboMechanics(unittest.TestCase):
    def setUp(self):
        self.game = Game(seed=42)

    def test_combo_rises_per_placement_not_per_tray(self):
        # R-3: combo aktualizuje się po każdym postawieniu.
        row_full_except(self.game, 7, filler=True)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 1)
        self.assertEqual(gained, 1 + 1 * 10)

        row_full_except(self.game, 7, filler=True)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 2)
        self.assertEqual(gained, 1 + 2 * 10)

    def test_combo_survives_two_placements_then_dies(self):
        # R-4: combo wygasa przez licznik, nie natychmiast.
        row_full_except(self.game, 7, filler=True)
        place_1x1(self.game, 7, 0)
        self.assertEqual(self.game.combo, 1)

        for placement in range(2):
            place_1x1(self.game, placement, 5)
            self.assertEqual(self.game.combo, 1, "combo zginęło za wcześnie")

        place_1x1(self.game, 2, 5)
        self.assertEqual(self.game.combo, 0, "combo powinno zginąć przy trzecim postawieniu")

    def test_full_clear_bonus(self):
        # R-5: 300, nie 100.
        self.game.combo = 6
        self.game.score = 1000
        row_full_except(self.game, 7)
        gained = place_1x1(self.game, 7, 0)
        # 1 komórka + combo 7 x B(1) w jednostce 15 + pusta plansza
        self.assertEqual(gained, 1 + 105 + FULL_CLEAR_BONUS)

    def test_no_full_clear_bonus_at_low_combo(self):
        # zmierzone w faza0: przy combo 1-5 pusta plansza nie daje bonusu
        row_full_except(self.game, 7)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(gained, 1 + 10)

    def test_no_full_clear_bonus_at_low_score(self):
        # zmierzone w faza0: faza0-8 n12 (combo 6, 301 pkt) bez bonusu, n23 (combo 4, 482 pkt) z bonusem
        self.game.combo = 5
        self.game.score = 301
        row_full_except(self.game, 7)
        gained = place_1x1(self.game, 7, 0)
        self.assertEqual(gained, 1 + 90)


class TestScoreAccumulates(unittest.TestCase):
    """Warunek wstępny #8 nr 1: bez tego benchmark nie ma czego czytać."""

    def test_score_is_cumulative(self):
        game = Game(seed=7)
        running = 0
        for _ in range(10):
            actions = game.available_actions()
            if not actions or game.done:
                break
            gained, score, _, _ = game.step(actions[0])
            running += gained
            self.assertEqual(score, running)
        self.assertGreater(game.score, 10)

    def test_placements_count_survival(self):
        game = Game(seed=7)
        moves = 0
        while not game.done:
            actions = game.available_actions()
            if not actions:
                break
            game.step(actions[0])
            moves += 1
        self.assertEqual(game.placements, moves)


class TestGenerator(unittest.TestCase):
    """Warunek wstępny #8 nr 2: R-9 — seed był ignorowany."""

    def test_same_seed_gives_same_pieces(self):
        a = [p.name for p in Generator(99).next_pieces()]
        b = [p.name for p in Generator(99).next_pieces()]
        self.assertEqual(a, b)

    def test_different_seeds_diverge(self):
        streams = set()
        for seed in range(20):
            gen = Generator(seed)
            streams.add(tuple(p.name for p in gen.next_pieces()))
        self.assertGreater(len(streams), 1)

    def test_whole_game_is_reproducible(self):
        def play(seed):
            game = Game(seed=seed)
            while not game.done:
                actions = game.available_actions()
                if not actions:
                    break
                game.step(actions[0])
            return game.score, game.placements

        self.assertEqual(play(2024), play(2024))


class TestPiecePool(unittest.TestCase):
    """R-6, R-7, R-8: pula i rozkład losowania."""

    def test_pool_has_41_poses(self):
        self.assertEqual(len(PIECE_POOL), EXPECTED_POSES)

    def test_no_duplicate_shapes(self):
        # R-7: "O" i "2x2" były tym samym klockiem, przez co 2x2 wypadał 2x częściej.
        shapes = [tuple(tuple(row) for row in p.shape) for p in PIECE_POOL]
        self.assertEqual(len(shapes), len(set(shapes)))

    def test_orientation_counts_match_reference(self):
        expected = {
            "1x1": 1, "beam2": 2, "beam3": 2, "beam4": 2, "beam5": 2,
            "square2": 1, "rect23": 2, "square3": 1, "corner3": 4,
            "L": 8, "corner5": 4, "diag2": 2, "diag3": 2, "S": 4, "T": 4,
        }
        actual = {
            name: len(PIECE_TYPES[i]) for i, (name, _) in enumerate(CANONICAL_TYPES)
        }
        self.assertEqual(actual, expected)

    def test_sampling_follows_measured_pose_counts(self):
        # Rozkład zmierzony w logach faza0 zastąpił model 1/15 na typ: częstość poz ~ POSE_COUNTS.
        from generator import POSE_COUNTS

        gen = Generator(1234)
        n = 20000
        counts = {}
        for _ in range(n):
            piece = gen._next_piece()
            counts[piece.name] = counts.get(piece.name, 0) + 1
        total = sum(POSE_COUNTS.values())
        for name in ("square2", "beam4-1", "L-7", "diag3-0"):
            expected = n * POSE_COUNTS[name] / total
            self.assertAlmostEqual(counts.get(name, 0), expected, delta=5 * expected ** 0.5 + 1)


class TestBenchmarkPrerequisites(unittest.TestCase):
    """Warunek wstępny #8 nr 3: agent musi umieć grać deterministycznie."""

    def test_agent_accepts_epsilon_zero(self):
        from agent import Agent

        agent = Agent()
        game = Game(seed=5)
        state = agent.get_state(game)
        agent.get_action(state[:3], epsilon=0.0)
        self.assertEqual(agent.epsilon, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
