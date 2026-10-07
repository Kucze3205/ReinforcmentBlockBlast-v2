"""Most bez emulatora: ekran podstawiony przez symulator, sprawdzamy koniec partii i pomiar.json."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import numpy as np
    import bridge
    from game import Game
except ImportError:   # most wymaga numpy i Pillow
    bridge = None


@unittest.skipIf(bridge is None, "brak numpy/Pillow")
class MostTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = {k: getattr(bridge, k) for k in (
            "OUT", "CEL", "LIMIT_S", "settled_state", "stable_state", "read_score", "in_game",
            "drag", "annotate", "screenshot")}
        self.saved_sleep, bridge.time.sleep = bridge.time.sleep, lambda s: None
        self.game = Game(seed=7)
        bridge.OUT = self.tmp.name
        bridge.CEL = bridge.LIMIT_S = 0
        bridge.settled_state = bridge.stable_state = self.screen
        bridge.read_score = lambda img: self.game.score
        bridge.screenshot = lambda: self.img
        bridge.in_game = lambda: True
        bridge.annotate = lambda *a: None
        bridge.drag = self.drag
        self.img = np.zeros((4, 4, 3))

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(bridge, k, v)
        bridge.time.sleep = self.saved_sleep
        self.tmp.cleanup()

    def screen(self):
        slots = [(p.shape, (40 + 100 * i, 500)) if p else None for i, p in enumerate(self.game.pieces)]
        return self.img, [row[:] for row in self.game.board.grid], slots

    def drag(self, center, piece, x, y):
        self.game.step((int((center[0] - 40) // 100), x, y))
        return {}, self.img

    def pomiar(self):
        return json.loads((Path(self.tmp.name) / "pomiar.json").read_text())

    def test_licznik_odrzuca_zle_odczyty(self):
        odczyty = iter([500, 500, 3995, 3995, 40, 40, 560, 560])
        bridge.read_score = lambda img: next(odczyty)
        self.assertEqual(bridge.read_counter(self.img, 497), 500)
        self.assertIsNone(bridge.read_counter(self.img, 500))   # skok 3495 > MAX_SKOK
        self.assertIsNone(bridge.read_counter(self.img, 500))   # licznik nie maleje
        self.assertEqual(bridge.read_counter(self.img, 500), 560)

    def test_gra_do_przegranej(self):
        bridge.main(100000)
        p = self.pomiar()
        self.assertEqual(p["koniec"], "przegrana")
        self.assertEqual(p["licznik"], self.game.score)
        self.assertEqual(p["ruchy"], self.game.placements)
        self.assertEqual(len(p["plansza"]), 8)
        self.assertLessEqual(len(p["ostatnie_ruchy"]), bridge.KEEP)

    def test_cel_konczy_partie(self):
        bridge.CEL = 150
        bridge.main(100000)
        p = self.pomiar()
        self.assertEqual(p["koniec"], "cel")
        self.assertGreaterEqual(p["licznik"], 150)

    def test_wyjatek_to_awaria(self):
        def boom(*a):
            raise RuntimeError("adb padł")
        bridge.drag = boom
        bridge.main(100000)
        p = self.pomiar()
        self.assertEqual(p["koniec"], "awaria")
        self.assertIn("adb padł", p["przyczyna"])

    def test_gra_poza_pierwszym_planem_to_przerwanie(self):
        bridge.in_game = lambda: False
        bridge.main(100000)
        self.assertEqual(self.pomiar()["koniec"], "przerwanie")

    def test_pusta_lista_ruchow_z_odczytu_nie_jest_przegrana_gdy_odczyt_sie_zmienia(self):
        # pierwszy odczyt: plansza pełna (animacja), drugi: poprawny stan gry
        pelna = [[1] * 8 for _ in range(8)]
        odczyty = iter([(self.img, pelna, self.screen()[2])])
        prawdziwy = self.screen
        bridge.settled_state = lambda: next(odczyty, None) or prawdziwy()
        bridge.stable_state = prawdziwy
        bridge.main(100000)
        self.assertEqual(self.pomiar()["koniec"], "przegrana")
        self.assertGreater(self.pomiar()["ruchy"], 0)


if __name__ == "__main__":
    unittest.main()
