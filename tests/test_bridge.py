"""Most bez emulatora: ekran podstawiony przez symulator, sprawdzamy koniec partii i pomiar.json."""
import json
import os
import shutil
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
            "drag", "annotate", "screenshot", "state_after", "read_board", "read_tray")}
        self.saved_sleep, bridge.time.sleep = bridge.time.sleep, lambda s: None
        self.game = Game(seed=7)
        bridge.OUT = self.tmp.name
        bridge.CEL = bridge.LIMIT_S = 0
        bridge.settled_state = bridge.stable_state = self.screen
        bridge.state_after = lambda expected, tray_left: bridge.readable(bridge.stable_state())
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
        odczyty = iter([500, 500, 10503, 10503, 40, 40, 560, 560])
        bridge.read_score = lambda img: next(odczyty)
        self.assertEqual(bridge.read_counter(self.img, 497), 500)
        self.assertIsNone(bridge.read_counter(self.img, 500))   # skok 10003 > MAX_SKOK (jak w logach faza0)
        self.assertIsNone(bridge.read_counter(self.img, 500))   # licznik nie maleje
        self.assertEqual(bridge.read_counter(self.img, 500), 560)

    @unittest.skipUnless(shutil.which("tesseract"), "brak tesseract")
    def test_odczyt_licznika_z_piatka_na_poczatku(self):
        # Zrzut z faza0 (partia 9, ruch 207): pełne pole czytane jako 59845, po przycięciu do tekstu 5845.
        from PIL import Image
        img = np.zeros((640, 320, 3), dtype=int)
        img[70:130, 60:260] = np.asarray(Image.open(ROOT / "tests" / "fixtures" / "licznik_5845.png").convert("RGB"))
        self.assertEqual(self.saved["read_score"](img), 5845)
        self.assertIsNone(self.saved["read_score"](np.zeros((640, 320, 3), dtype=int)))

    def klatki(self, odczyty):
        """screenshot() oddaje kolejne numery klatek, odczyt planszy i tacki bierze je z listy (plansza, tacka)."""
        it = iter(range(len(odczyty)))
        bridge.screenshot = lambda: next(it)
        bridge.read_board = lambda k: odczyty[k][0]
        bridge.read_tray = lambda k: odczyty[k][1]

    def test_stan_po_ruchu_dwie_zgodne_klatki_bez_wolnego_odczytu(self):
        bridge.state_after = self.saved["state_after"]
        pusta, po = [[0] * 8 for _ in range(8)], [[1] + [0] * 7] + [[0] * 8 for _ in range(7)]
        klocek = [[1]]
        reszta = [None, (klocek, (140, 500)), None]
        self.klatki([(pusta, reszta), (po, [None, (klocek, (150, 520)), None]), (po, reszta), (po, reszta)])
        bridge.stable_state = lambda: self.fail("wolny odczyt")
        img, grid, slots = bridge.state_after(po, [None, klocek, None])
        self.assertEqual((img, grid, slots), (3, po, reszta))

    def test_stan_po_ruchu_po_ostatnim_klocku_czeka_na_trzy_nowe(self):
        bridge.state_after = self.saved["state_after"]
        po = [[0] * 8 for _ in range(8)]
        nowe = [([[1]], (40 + 100 * i, 500)) for i in range(3)]
        self.klatki([(po, [None] * 3), (po, [None] * 3), (po, nowe[:2] + [None]), (po, nowe), (po, nowe)])
        self.assertEqual(bridge.state_after(po, [None] * 3)[2], nowe)

    def test_stan_po_ruchu_rozbieznosc_wraca_do_wolnego_odczytu(self):
        bridge.state_after = self.saved["state_after"]
        inna = [[1] * 8] + [[0] * 8 for _ in range(7)]
        self.klatki([(inna, [None] * 3)] * bridge.ZRZUTY_PO_RUCHU)
        bridge.stable_state = lambda: ("wolny", inna, [None] * 3)
        self.assertEqual(bridge.state_after([[0] * 8 for _ in range(8)], [None] * 3)[0], "wolny")

    def test_licznik_co_kilka_ruchow_i_przed_przegrana(self):
        bridge.main(100000)
        wpisy = [json.loads(l) for l in (Path(self.tmp.name) / "moves.jsonl").read_text().splitlines()]
        z_licznikiem = [w["n"] for w in wpisy if w["score"] is not None]
        self.assertEqual(z_licznikiem[:3], [0, bridge.LICZNIK_CO, 2 * bridge.LICZNIK_CO])
        self.assertEqual(z_licznikiem[-1], wpisy[-1]["n"])
        self.assertEqual(self.pomiar()["licznik"], self.game.score)

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

    def test_ekran_konca_gry_nie_trafia_do_logu_jako_tacka(self):
        # po przegranej ekran końca gry czytany jak tacka daje "klocki" 9x7 (logi faza0): miara klocków liczyła je jako nieznane
        smiec = [([[1] * 7 for _ in range(9)], (40, 500)), ([[1] * 7, [1] * 7], (140, 500)), None]
        self.assertFalse(bridge.tray_ok(smiec))
        self.assertTrue(bridge.tray_ok(self.screen()[2]))
        prawdziwy = self.screen
        bridge.settled_state = bridge.stable_state = lambda: (
            (self.img, [row[:] for row in self.game.board.grid], smiec) if self.game.done else prawdziwy())
        bridge.main(100000)
        p = self.pomiar()
        self.assertEqual(p["koniec"], "przegrana")
        self.assertEqual(p["ruchy"], self.game.placements)
        wpisy = [json.loads(l) for l in (Path(self.tmp.name) / "moves.jsonl").read_text().splitlines()]
        self.assertEqual(wpisy[-1]["tray"], [None, None, None])
        self.assertIn("end", wpisy[-1])
        for w in wpisy:
            self.assertTrue(all(s is None or max(len(s), len(s[0])) <= bridge.MAX_KLOCEK for s in w["tray"]))

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
