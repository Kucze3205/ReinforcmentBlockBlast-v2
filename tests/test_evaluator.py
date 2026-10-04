"""Testy ewaluatora: rozdania, hash, nakładka, ocena symulatorem, seria, s_v i bramka."""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ocena", ROOT / ".github" / "evaluator" / "ocena.py")
ocena = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ocena)

CFG = ocena.config()


def zapisz(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj), encoding="utf-8")


def pomiar(dir_, k, koniec, licznik=None, **extra):
    zapisz(Path(dir_) / ("seria-x-partia-%d" % k) / "pomiar.json",
           dict(koniec=koniec, licznik=licznik, ruchy=10, czas_s=1.0, przyczyna=extra.pop("przyczyna", None), **extra))


class RozdaniaTest(unittest.TestCase):
    def test_stale_w_drzewie_rozne_miedzy_drzewami(self):
        a = ocena.rozdania("1", 20, salt="s")
        self.assertEqual(a, ocena.rozdania("1", 20, salt="s"))
        self.assertNotEqual(a, ocena.rozdania("2", 20, salt="s"))
        self.assertNotEqual(a, ocena.rozdania("1", 20, salt="inna"))

    def test_bez_soli_blad(self):
        os.environ.pop("DEALS_SALT", None)
        with self.assertRaises(SystemExit):
            ocena.rozdania("1", 5)


class HashTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for rel in CFG["tylko_do_odczytu"]["sym"] + CFG["tylko_do_odczytu"]["most"] + [ocena.SERIA_YML, ocena.OCENA_PY]:
            dst = Path(self.tmp) / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, dst)
        self.old_root, ocena.ROOT = ocena.ROOT, Path(self.tmp)

    def tearDown(self):
        ocena.ROOT = self.old_root
        shutil.rmtree(self.tmp)

    def test_hash_jest_dzielony(self):
        s0, m0 = ocena.hash_sym("d"), ocena.hash_most()
        (Path(self.tmp) / "bridge.py").write_text("# naprawa mostu")
        self.assertEqual(ocena.hash_sym("d"), s0)
        self.assertNotEqual(ocena.hash_most(), m0)
        m1 = ocena.hash_most()
        (Path(self.tmp) / "generator.py").write_text("# kalibracja")
        self.assertEqual(ocena.hash_most(), m1)
        self.assertNotEqual(ocena.hash_sym("d"), s0)

    def test_rozdania_wchodza_do_hasha_symulatora(self):
        self.assertNotEqual(ocena.hash_sym("a"), ocena.hash_sym("b"))


class NakladkaTest(unittest.TestCase):
    def test_pliki_ewaluatora_nadpisuja_wezel(self):
        with tempfile.TemporaryDirectory() as node:
            (Path(node) / "scoring.py").write_text("FULL_CLEAR_BONUS = 10**9")
            (Path(node) / "agent.py").write_text("# kod agenta")
            ocena.nakladka(node)
            self.assertEqual((Path(node) / "scoring.py").read_bytes(), (ROOT / "scoring.py").read_bytes())
            self.assertEqual((Path(node) / "agent.py").read_text(), "# kod agenta")


class SymTest(unittest.TestCase):
    def test_ocena_i_zliczenie_shardow(self):
        small = dict(CFG, rozdania=6, cap=40)
        old_cfg, ocena.config = ocena.config, lambda: small
        cwd, path = os.getcwd(), list(sys.path)
        try:
            with tempfile.TemporaryDirectory() as d:
                for s in (0, 1):
                    os.environ["DEALS_SALT"] = "test"   # sym zabiera sól z środowiska
                    ocena.sym(str(ROOT), "1", s, 2, "%s/sym-%d.json" % (d, s))
                pelna = ocena.zlicz_sym(d, small)
                self.assertEqual(len(pelna["przezycie"]), 6)
                self.assertFalse(pelna["za_wolna"])
                self.assertEqual(pelna["przegrane"], sum(r < 40 for r in pelna["przezycie"]))
                self.assertTrue(0 < pelna["s_sym"] <= 1)
                os.remove("%s/sym-1.json" % d)
                self.assertTrue(ocena.zlicz_sym(d, small)["za_wolna"])
        finally:
            ocena.config = old_cfg
            os.chdir(cwd)
            sys.path[:] = path
            os.environ.pop("DEALS_SALT", None)

    def test_wyjatek_w_build_daje_zero(self):
        with tempfile.TemporaryDirectory() as node, tempfile.TemporaryDirectory() as out:
            for rel in CFG["tylko_do_odczytu"]["sym"]:
                shutil.copyfile(ROOT / rel, Path(node) / rel)
            (Path(node) / "policies.py").write_text("def build(weights=None):\n    raise RuntimeError('wagi nie pasuja')\n")
            env = dict(os.environ, DEALS_SALT="test")
            subprocess.run([sys.executable, str(ROOT / ".github/evaluator/ocena.py"), "sym", node,
                            "--drzewo", "1", "--shard", "0/10", "--out", out + "/sym-0.json"], check=True, env=env)
            rec = json.loads(Path(out + "/sym-0.json").read_text())
            self.assertIn("wagi nie pasuja", rec["blad"])
            self.assertTrue(rec["gry"] and all(g["ruchy"] == 0 for g in rec["gry"]))
            wynik = ocena.zlicz_sym(out, dict(CFG, rozdania=len(rec["gry"])))
            self.assertEqual(wynik["s_sym"], 0.0)


class SymOcenaTest(unittest.TestCase):
    def zlicz(self, ruchy, punkty=0):
        with tempfile.TemporaryDirectory() as d:
            zapisz(d + "/sym-0.json", {"hash_sym": "h", "blad": None,
                                       "gry": [{"i": i, "ruchy": r, "punkty": punkty} for i, r in enumerate(ruchy)]})
            return ocena.zlicz_sym(d, dict(CFG, rozdania=len(ruchy)))

    def test_przezycie_do_capa_to_nie_przegrana(self):
        o = self.zlicz([CFG["cap"]] * 3)
        self.assertEqual((o["przegrane"], o["s_sym"]), (0, 1.0))

    def test_punkty_tylko_rozstrzygaja_remis_nigdy_nie_przebijaja_przezycia(self):
        cap = CFG["cap"]
        slabszy_bogatszy = self.zlicz([cap] * 299 + [cap - 1], punkty=10**7)
        mocniejszy = self.zlicz([cap] * 300)
        self.assertLess(slabszy_bogatszy["s_sym"], mocniejszy["s_sym"])
        self.assertLess(self.zlicz([100] * 300)["s_sym"], self.zlicz([100] * 299 + [101])["s_sym"])
        self.assertLess(self.zlicz([100] * 300)["s_sym"], self.zlicz([100] * 300, punkty=500)["s_sym"])


class SeriaTest(unittest.TestCase):
    def test_klasyfikacja_i_s_emu(self):
        with tempfile.TemporaryDirectory() as d:
            pomiar(d, 1, "cel", 1_000_050)
            pomiar(d, 2, "przegrana", 400_000, plansza=[[1]], ostatnie_ruchy=[{"n": 1}])
            pomiar(d, 3, "przerwanie", 10, przyczyna="limit czasu partii")
            (Path(d) / "seria-x-partia-4").mkdir()
            ok, niewazne = ocena.zlicz_seria(d, CFG)
            self.assertEqual(sorted(ok), [1, 2])
            self.assertEqual([n["partia"] for n in niewazne], [3, 4])
            self.assertEqual(niewazne[1]["koniec"], "awaria")
            self.assertIn("plansza", ok[2])
            self.assertNotIn("plansza", ok[1])
            self.assertAlmostEqual(ocena.s_emu(ok, CFG), (1.0 + 0.4) / 2)

    def test_s_emu_przegrana_po_milionie_licznika_liczy_sie_jako_przegrana_w_bramce(self):
        partie = {str(k): {"koniec": "cel", "licznik": 1_000_001} for k in range(1, 10)}
        partie["10"] = {"koniec": "przegrana", "licznik": 5_000_000}
        self.assertFalse(ocena.bramka({"emu": {"partie": partie}}))


class ZliczTest(unittest.TestCase):
    def run_zlicz(self, ruchy, seria=None, poprzednia=None):
        with tempfile.TemporaryDirectory() as d:
            zapisz(d + "/sym/sym-0.json", {"hash_sym": "h", "blad": None,
                                           "gry": [{"i": i, "ruchy": r, "punkty": 0} for i, r in enumerate(ruchy)]})
            cfg, ocena.config = ocena.config, lambda: dict(CFG, rozdania=len(ruchy))
            try:
                return ocena.zlicz("1", d + "/sym", seria, poprzednia, "abc")
            finally:
                ocena.config = cfg

    def test_przegrana_w_symulatorze_zamyka_ocene_bez_serii(self):
        o = self.run_zlicz([5, CFG["cap"]])
        self.assertEqual((o["status"], o["potrzebna_seria"], o["brakujace_partie"]), ("gotowa", False, []))
        self.assertLess(ocena.s_v(o["sym"], o["emu"]), 1.0)

    def test_zero_przegranych_wymaga_serii_a_bez_niej_s_v_to_1(self):
        o = self.run_zlicz([CFG["cap"]] * 3)
        self.assertEqual((o["status"], o["potrzebna_seria"]), ("w_toku", True))
        self.assertEqual(o["brakujace_partie"], list(range(1, 11)))
        self.assertEqual(ocena.s_v(o["sym"], o["emu"]), 1.0)

    def test_pelna_seria_podnosi_s_v_nad_kazdy_wezel_bez_serii(self):
        with tempfile.TemporaryDirectory() as d:
            for k in range(1, 11):
                pomiar(d, k, "przegrana", 100_000)
            o = self.run_zlicz([CFG["cap"]] * 3, seria=d)
            self.assertEqual(o["status"], "gotowa")
            self.assertAlmostEqual(ocena.s_v(o["sym"], o["emu"]), 1.1)
            self.assertFalse(ocena.bramka(o))

    def test_powtorka_scala_wazne_partie_z_poprzednia_ocena(self):
        with tempfile.TemporaryDirectory() as d:
            for k in range(1, 9):
                pomiar(d + "/a", k, "cel", 1_000_001)
            for k in (9, 10):
                pomiar(d + "/a", k, "przerwanie", None, przyczyna="gra zniknela")
            pierwsza = self.run_zlicz([CFG["cap"]] * 3, seria=d + "/a")
            self.assertEqual((pierwsza["status"], pierwsza["brakujace_partie"]), ("w_toku", [9, 10]))
            zapisz(d + "/prev.json", pierwsza)
            for k in (9, 10):
                pomiar(d + "/b", k, "cel", 1_000_001)
            koniec = self.run_zlicz([CFG["cap"]] * 3, seria=d + "/b", poprzednia=d + "/prev.json")
            self.assertEqual(koniec["status"], "gotowa")
            self.assertEqual(koniec["emu"]["niewazne"], [])
            self.assertTrue(ocena.bramka(koniec))
            self.assertAlmostEqual(ocena.s_v(koniec["sym"], koniec["emu"]), 2.0)


class ZapiszTest(unittest.TestCase):
    def ocena(self, ruchy, seria=None, hash_="h1", czas_s=0):
        with tempfile.TemporaryDirectory() as d:
            zapisz(d + "/sym/sym-0.json", {"hash_sym": hash_, "blad": None, "czas_s": czas_s,
                                           "gry": [{"i": i, "ruchy": r, "punkty": 0} for i, r in enumerate(ruchy)]})
            cfg, ocena.config = ocena.config, lambda: dict(CFG, rozdania=len(ruchy))
            try:
                return ocena.zlicz("1", d + "/sym", seria, None, "abc")
            finally:
                ocena.config = cfg

    def rekord(self, d, **extra):
        path = Path(d) / "1.1.json"
        zapisz(path, dict({"stan": "ocena w toku", "oczekiwanie_min": 0.0}, **extra))
        return path

    def test_przegrana_w_symulatorze_oznacza_wezel_jako_oceniony(self):
        with tempfile.TemporaryDirectory() as d:
            rek = self.rekord(d)
            ocena.zapisz(self.ocena([5, CFG["cap"]]), rek, d + "/cel.json")
            rec = json.loads(rek.read_text())
            self.assertEqual(rec["stan"], "oceniony")
            self.assertEqual(list(rec["oceny"]["s_sym"]), ["h1"])
            self.assertNotIn("s_emu", rec["oceny"])
            self.assertEqual(rec["oczekiwanie_min"], 0.0)
            self.assertFalse((Path(d) / "cel.json").exists())

    def test_czas_symulatora_zostaje_z_nagrania(self):
        with tempfile.TemporaryDirectory() as d:
            rek = self.rekord(d)
            ocena.zapisz(self.ocena([5, 7], hash_="h1", czas_s=600), rek, d + "/cel.json")
            ocena.zapisz(self.ocena([9, 9], hash_="h2", czas_s=60), rek, d + "/cel.json")
            self.assertEqual(json.loads(rek.read_text())["oceny"]["czas_sym_min"], 10.0)

    def test_przeliczenie_dopisuje_wersje_zamiast_nadpisywac(self):
        with tempfile.TemporaryDirectory() as d:
            rek = self.rekord(d)
            ocena.zapisz(self.ocena([5, 7], hash_="h1"), rek, d + "/cel.json")
            ocena.zapisz(self.ocena([9, 9], hash_="h2"), rek, d + "/cel.json")
            self.assertEqual(list(json.loads(rek.read_text())["oceny"]["s_sym"]), ["h1", "h2"])

    def test_seria_w_toku_nie_daje_s_emu_a_pelna_tak(self):
        with tempfile.TemporaryDirectory() as d:
            rek = self.rekord(d)
            for k in range(1, 8):
                pomiar(d + "/s", k, "przegrana", 100_000)
            ocena.zapisz(self.ocena([CFG["cap"]] * 3, seria=d + "/s"), rek, d + "/cel.json")
            rec = json.loads(rek.read_text())
            self.assertEqual(rec["stan"], "ocena w toku")
            self.assertNotIn("s_emu", rec["oceny"])
            for k in range(8, 11):
                pomiar(d + "/s", k, "przegrana", 100_000)
            ocena.zapisz(self.ocena([CFG["cap"]] * 3, seria=d + "/s"), rek, d + "/cel.json")
            rec = json.loads(rek.read_text())
            self.assertEqual(rec["stan"], "oceniony")
            self.assertAlmostEqual(rec["oceny"]["s_emu"], 0.1)
            self.assertEqual(rec["oceny"]["czas_serii_min"], round(1.0 / 60, 1))

    def test_bramka_zaklada_znacznik_konca_petli(self):
        with tempfile.TemporaryDirectory() as d:
            rek = self.rekord(d)
            for k in range(1, 11):
                pomiar(d + "/s", k, "cel", 1_000_000)
            ocena.zapisz(self.ocena([CFG["cap"]] * 3, seria=d + "/s"), rek, d + "/cel.json")
            self.assertEqual(json.loads((Path(d) / "cel.json").read_text())["drzewo"], "1")


class BramkaTest(unittest.TestCase):
    def test_jedna_przegrana_albo_brak_partii_nie_otwiera_bramki(self):
        cel = {"koniec": "cel", "licznik": 1_000_001}
        pelna = {str(k): cel for k in range(1, 11)}
        self.assertTrue(ocena.bramka({"emu": {"partie": pelna}}))
        self.assertFalse(ocena.bramka({"emu": {"partie": dict(pelna, **{"3": {"koniec": "przegrana", "licznik": 5}})}}))
        self.assertFalse(ocena.bramka({"emu": {"partie": {"1": cel}}}))
        self.assertFalse(ocena.bramka({"emu": None}))


class KontraktTest(unittest.TestCase):
    def test_polityka_wezla_ma_interfejs_mostu_i_symulatora(self):
        sys.path.insert(0, str(ROOT))
        try:
            import policies
            p = policies.build(None)
            self.assertTrue(callable(p.reset) and callable(p.act))
        finally:
            sys.path.remove(str(ROOT))

    def test_liczby_w_workflowach_zgadzaja_sie_z_konfiguracja(self):
        seria = (ROOT / ".github/workflows/seria.yml").read_text(encoding="utf-8")
        ocena_yml = (ROOT / ".github/workflows/ocena.yml").read_text(encoding="utf-8")
        self.assertIn("[%s]" % ",".join(str(k) for k in range(1, CFG["partie"] + 1)), seria.replace(" ", ""))
        shardy = re.search(r"shard: \[([\d, ]+)\]", ocena_yml).group(1).split(",")
        self.assertIn("matrix.shard }}/%d" % len(shardy), ocena_yml)
        self.assertLess(CFG["limit_shardu_s"], 60 * int(re.search(r"timeout-minutes: (\d+)", ocena_yml).group(1)))


if __name__ == "__main__":
    unittest.main()
