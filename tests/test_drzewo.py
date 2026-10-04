"""Testy harmonogramu drzewa: polityka startowa, paczka, czas T, kroki i zamknięcie drzewa."""
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".github", "loop"))
import loop  # noqa: E402
import drzewo  # noqa: E402

policy, DIGEST = drzewo.load_policy(ROOT)
CFG = drzewo.config(ROOT)


def rec(node, s, minuty=60, eval_min=0, sha=None, parent_sha="K"):
    chain, depth = node.split(".")
    parent = "%s.%d" % (chain, int(depth) - 1) if int(depth) > 1 else "korzen"
    return {"rodzic": parent, "rodzic_sha": parent_sha, "kolejnosc": 1, "sha": sha or node, "stan": "oceniony",
            "koszt": {"tury": 1, "usd": 0, "minuty": minuty}, "oczekiwanie_min": 999,
            "oceny": {"s_sym": {"h": s}, "czas_sym_min": eval_min}}


def question(recs, baseline=0.0, runda=0):
    return drzewo.Pytanie(drzewo.obserwacje(recs, baseline), CFG["W"], CFG["K"], runda, baseline)


class PolitykaStartowaTest(unittest.TestCase):
    def test_pierwsza_runda_otwiera_pelne_W_lancuchow(self):
        self.assertEqual(policy.solve(question({})), [None] * CFG["W"])

    def test_kontynuuje_lancuchy_z_poprawa(self):
        recs = {"1.1": rec("1.1", 0.2), "2.1": rec("2.1", 0.3)}
        self.assertEqual(policy.solve(question(recs)), ["1.1", "2.1"])

    def test_dwa_nietrafienia_z_rzedu_zamykaja_lancuch(self):
        recs = {"1.1": rec("1.1", 0.2), "1.2": rec("1.2", 0.2), "1.3": rec("1.3", 0.1),
                "2.1": rec("2.1", 0.3), "2.2": rec("2.2", 0.1), "2.3": rec("2.3", 0.5)}
        self.assertEqual(policy.solve(question(recs)), ["2.3"])

    def test_pierwszy_wezel_porownany_z_baseline(self):
        recs = {"1.1": rec("1.1", 0.2), "1.2": rec("1.2", 0.2)}
        self.assertEqual(policy.solve(question(recs, baseline=0.5)), [])

    def test_wszystkie_lancuchy_martwe_to_pusta_paczka(self):
        recs = {"1.1": rec("1.1", 0.0), "1.2": rec("1.2", 0.0)}
        self.assertEqual(policy.solve(question(recs)), [])

    def test_deterministyczna(self):
        recs = {"2.1": rec("2.1", 0.3), "1.1": rec("1.1", 0.2)}
        self.assertEqual(policy.solve(question(recs)), policy.solve(question(recs)))


class PaczkaTest(unittest.TestCase):
    def test_odrzuca_niedozwolone_i_obcina_do_W(self):
        q = question({"1.1": rec("1.1", 0.2), "2.1": rec("2.1", 0.2)})
        self.assertEqual(drzewo.paczka(["1.1", "1.1", "9.9", 5, "1.0", None, "2.1", None, None], q),
                         ["1.1", None, "2.1", None])
        self.assertEqual(drzewo.paczka(None, q), [])

    def test_liscie_to_czubki_lancuchow(self):
        q = question({"1.1": rec("1.1", 0.2), "1.2": rec("1.2", 0.2)})
        self.assertEqual(q.legal_actions(), [None, "1.2"])
        self.assertEqual(drzewo.paczka(["1.1"], q), [])

    def test_nazwy_wezlow(self):
        self.assertEqual(drzewo.nazwij([None, "1.2", None], [["1.1", "2.1"], ["1.2"]]), ["3.1", "1.3", "4.1"])
        self.assertEqual(drzewo.nazwij([None], []), ["1.1"])


class CzasTest(unittest.TestCase):
    def test_paczka_kosztuje_najdluzszy_wezel_T_to_suma(self):
        recs = {"1.1": rec("1.1", 0.5, minuty=60, eval_min=30), "2.1": rec("2.1", 0.4, minuty=120),
                "1.2": rec("1.2", 0.6, minuty=30)}
        recs["1.1"]["oceny"]["czas_serii_min"] = 90
        self.assertAlmostEqual(drzewo.czas_h([["1.1", "2.1"], ["1.2"]], recs), 3.0 + 0.5)

    def test_oczekiwanie_poza_kosztem(self):
        self.assertAlmostEqual(drzewo.koszt_h(rec("1.1", 0.1, minuty=120)), 2.0)

    def test_wezel_dziedziczony_nie_placi_za_ocene_drugi_raz(self):
        r = rec("1.2", 0.1, minuty=6, eval_min=600, sha="A", parent_sha="A")
        self.assertAlmostEqual(drzewo.koszt_h(r), 0.1)
        r = rec("1.1", 0.1, minuty=6, eval_min=600, sha="K", parent_sha="K")   # rodzic to korzeń: oceniany
        self.assertAlmostEqual(drzewo.koszt_h(r), 10.1)

    def test_wezly_spoza_nagrania_nie_licza_sie(self):
        recs = {"1.1": rec("1.1", 0.5, minuty=60)}
        self.assertAlmostEqual(drzewo.czas_h([["1.1", "2.1"], ["1.2"]], recs), 1.0)

    def test_V_to_max_s_v_minus_beta_T(self):
        recs = {"1.1": rec("1.1", 0.5, minuty=600), "2.1": rec("2.1", 0.7, minuty=60)}
        self.assertAlmostEqual(drzewo.wartosc([["1.1", "2.1"]], recs, 0.01), 0.7 - 0.01 * 10)

    def test_V_serii_to_1_plus_s_emu(self):
        r = rec("1.1", 0.5)
        r["oceny"]["s_emu"] = 0.25
        self.assertAlmostEqual(drzewo.wartosc([["1.1"]], {"1.1": r}, 0), 1.25)


class KrokTest(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)

    def krok(self, tree=1, cel=False, cfg=CFG, pol=policy, digest=DIGEST):
        return drzewo.krok(self.base, tree, pol, digest, cfg, cel)

    def zapisz_wezly(self, tree, recs):
        for n, r in recs.items():
            loop.write_json(loop.record_path(self.base, tree, n), r)

    def stan(self, tree=1):
        return drzewo.read_state(self.base, tree)

    def test_pierwszy_krok_otwiera_paczke_z_kolejnoscia(self):
        self.assertEqual(self.krok(), [("WEZEL", 1, "%d.1" % i, i) for i in range(1, 5)])
        self.assertEqual(self.stan()["paczki"], [["1.1", "2.1", "3.1", "4.1"]])

    def test_powtorzony_krok_czeka_na_ocene_paczki(self):
        self.krok()
        self.assertEqual(self.krok(), [])
        self.zapisz_wezly(1, {n: rec(n, 0.1) for n in ("1.1", "2.1", "3.1")})
        self.assertEqual(self.krok(), [])
        self.assertEqual(len(self.stan()["paczki"]), 1)

    def test_nastepna_runda_po_ocenie_calej_paczki(self):
        self.krok()
        self.zapisz_wezly(1, {"1.1": rec("1.1", 0.1), "2.1": rec("2.1", 0.2), "3.1": rec("3.1", 0.0), "4.1": rec("4.1", 0.3)})
        self.assertEqual(self.krok(), [("WEZEL", 1, "1.2", 5), ("WEZEL", 1, "2.2", 6), ("WEZEL", 1, "3.2", 7), ("WEZEL", 1, "4.2", 8)])

    def test_pusta_paczka_zamyka_drzewo_i_wyzwala_offline(self):
        self.krok()
        self.zapisz_wezly(1, {n: rec(n, 0.0, minuty=60) for n in ("1.1", "2.1", "3.1", "4.1")})
        self.krok()   # delta 0 to dopiero jedno nietrafienie: łańcuchy idą dalej
        self.zapisz_wezly(1, {n: rec(n, 0.0, minuty=60) for n in ("1.2", "2.2", "3.2", "4.2")})
        self.assertEqual(self.krok(), [("OFFLINE", 1)])
        koniec = self.stan()["koniec"]
        self.assertEqual(koniec["powod"], "pusta paczka")
        self.assertAlmostEqual(koniec["T_h"], 2.0)
        self.assertEqual(self.krok(), [])

    def test_K_rund_zamyka_drzewo(self):
        cfg = dict(CFG, K=1)
        self.krok(cfg=cfg)
        self.zapisz_wezly(1, {n: rec(n, 0.1) for n in ("1.1", "2.1", "3.1", "4.1")})
        self.assertEqual(self.krok(cfg=cfg), [("OFFLINE", 1)])
        self.assertEqual(self.stan()["koniec"]["powod"], "K")

    def test_cel_zamyka_drzewo_bez_offline_i_nic_nie_zaczyna(self):
        self.krok()
        self.assertEqual(self.krok(cel=True), [])
        self.assertEqual(self.stan()["koniec"]["powod"], "cel")
        self.assertEqual(self.krok(tree=2, cel=True), [])
        self.assertIsNone(self.stan(2))

    def test_polityka_zmieniona_w_trakcie_drzewa_to_blad(self):
        self.krok()
        with self.assertRaises(SystemExit):
            self.krok(digest="inny")

    def test_numer_drzewa(self):
        self.assertEqual(drzewo.next_tree(self.base), 1)
        self.krok()
        self.assertEqual(drzewo.next_tree(self.base), 1)
        self.krok(cel=True)
        self.assertEqual(drzewo.next_tree(self.base), 2)

    def test_polityka_zwracajaca_smieci_nie_psuje_drzewa(self):
        class Zla:
            @staticmethod
            def solve(q):
                return ["9.9", 7, None] * 5
        self.assertEqual(self.krok(pol=Zla), [("WEZEL", 1, "%d.1" % i, i) for i in range(1, CFG["W"] + 1)])


class NazwyTest(unittest.TestCase):
    def test_kod_harmonogramu_nie_zna_nazw_algorytmu(self):
        for rel in (".github/policy/policy.py", ".github/loop/drzewo.py"):
            with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                text = fh.read().lower()
            for word in ("dream", "rsi", "paper", "eksperyment", "v1"):
                self.assertNotIn(word, text, rel)


if __name__ == "__main__":
    unittest.main()
