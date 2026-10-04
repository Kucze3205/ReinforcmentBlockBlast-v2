"""Testy kalibracji: miary rozjazdu na logach mostu, bramka naprawy, wyzwalacze utrzymania, hash i ścieżki."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("kalibracja", ROOT / ".github" / "evaluator" / "kalibracja.py")
kal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kal)

CFG = kal.cfg()
K = CFG["kalibracja"]
MOD = kal.sim(ROOT)


def zagraj(seed, skala=1.0, limit=400):
    """Partia zachłanna w symulatorze zapisana jak `moves.jsonl` mostu (licznik przed ruchem)."""
    from policies import GreedyPolicy
    game, policy, wpisy = MOD.game.Game(seed=seed), GreedyPolicy(), []
    while not game.done and len(wpisy) < limit:
        i, x, y = policy.act(game, game.available_actions())
        wpisy.append({"n": len(wpisy), "board": [r[:] for r in game.board.grid], "score": int(game.score * skala),
                      "tray": [None if p is None else p.shape for p in game.pieces], "move": {"slot": i, "x": x, "y": y}})
        game.step((i, x, y))
    wpisy.append({"n": len(wpisy), "board": [r[:] for r in game.board.grid], "score": int(game.score * skala),
                  "tray": [None if p is None else p.shape for p in game.pieces]})
    return wpisy


def zapisz_logi(dir_, partie, nazwa="moves.jsonl"):
    for k, wpisy in enumerate(partie, 1):
        d = Path(dir_) / ("seria-x-partia-%d" % k)
        d.mkdir(parents=True, exist_ok=True)
        (d / nazwa).write_text("\n".join(json.dumps(w) for w in wpisy), encoding="utf-8")


def pomiar(dir_, k, koniec, przyczyna=None):
    d = Path(dir_) / ("seria-x-partia-%d" % k)
    d.mkdir(parents=True, exist_ok=True)
    (d / "pomiar.json").write_text(json.dumps({"koniec": koniec, "licznik": 5, "ruchy": 3, "czas_s": 1.0, "przyczyna": przyczyna}))


PARTIE = [zagraj(s) for s in range(1, 13)]


class ChiKwadratTest(unittest.TestCase):
    def test_gamma_q_zgadza_sie_ze_scipy(self):
        try:
            from scipy.stats import chi2
        except ImportError:
            self.skipTest("brak scipy")
        for df in (1, 5, 17, 40):
            for x in (0.3, df * 0.5, df, df * 2, df * 3):
                self.assertAlmostEqual(kal.gamma_q(df / 2, x / 2), chi2.sf(x, df), places=9)


class MiaryTest(unittest.TestCase):
    def test_zgodne_logi_sa_w_tolerancji(self):
        m = kal.mierz(PARTIE, MOD, K)
        self.assertEqual(m["tempo"]["stosunek"], 1.0)
        self.assertTrue(m["klocki"]["ok"], m["klocki"])
        self.assertTrue(m["ok"])

    def test_tempo_poza_tolerancja_w_obie_strony(self):
        for skala, ok in ((1.1, True), (1.3, False), (0.7, False)):
            t = kal.tempo([zagraj(s, skala) for s in range(1, 13)], MOD, K)
            self.assertIs(t["ok"], ok, (skala, t))

    def test_nieczytelny_licznik_to_brak_danych_nie_zgoda(self):
        bez = [[dict(w, score=None) for w in p] for p in PARTIE]
        self.assertIsNone(kal.tempo(bez, MOD, K)["ok"])
        self.assertFalse(kal.mierz(bez, MOD, K)["ok"])

    def test_zly_odczyt_licznika_nie_psuje_tempa(self):
        zle = [[dict(w) for w in p] for p in PARTIE]
        zle[0][5]["score"] = 10**9      # OCR dopisał cyfry
        self.assertIs(kal.tempo(zle, MOD, K)["ok"], True)

    def test_combo_przechodzi_przez_odczyty_bez_licznika(self):
        dziury = [[dict(w, score=None) if i % 4 == 1 else w for i, w in enumerate(p)] for p in PARTIE]
        self.assertAlmostEqual(kal.tempo(dziury, MOD, K)["stosunek"], 1.0, places=6)

    def tacki(self, shapes, n=200):
        return [[{"n": i, "board": [[0] * 8 for _ in range(8)], "tray": shapes, "score": 0} for i in range(n)]]

    def test_rozklad_klockow_skosny_odpada(self):
        jeden = [p.shape for p in MOD.pieces.PIECE_POOL[:1]] * 3
        # kolejne wpisy z tą samą tacką to powtórki po nieudanym ruchu, więc przeplatamy z pustą
        wpisy = []
        for i in range(200):
            wpisy += [{"n": 2 * i, "board": [], "tray": jeden, "score": 0}, {"n": 2 * i + 1, "board": [], "tray": [None] * 3, "score": 0}]
        kl = kal.klocki([wpisy], MOD, K)
        self.assertFalse(kl["ok"], kl)
        self.assertLess(kl["p"], 1e-6)

    def test_powtorzona_tacka_po_nieudanym_ruchu_liczy_sie_raz(self):
        shapes = [p.shape for p in MOD.pieces.PIECE_POOL[:3]]
        kl = kal.klocki(self.tacki(shapes), MOD, K)
        self.assertEqual(kl["n"], 3)
        self.assertIsNone(kl["ok"])   # za mało klocków na test

    def test_nieznany_ksztalt_to_blad_odczytu(self):
        wpisy = [dict(w) for w in PARTIE[0]]
        wpisy2 = [dict(w) for p in PARTIE for w in p]
        for w in wpisy2[::3]:
            if w["tray"] and all(s is not None for s in w["tray"]):
                w["tray"] = [[[1, 1, 1, 1, 1, 1, 1]]] * 3     # nieistniejąca belka 1x7
        self.assertFalse(kal.klocki([wpisy2], MOD, K)["ok"])

    def test_malo_klockow_to_brak_danych(self):
        self.assertIsNone(kal.klocki([PARTIE[0][:5]], MOD, K)["ok"])

    def test_kosze_zlewaja_male_poz(self):
        p = kal.wzorzec(MOD, 5000)
        for b in kal.kosze(p, 300):
            self.assertGreaterEqual(sum(p[i] for i in b) * 300, 5.0)
        self.assertEqual(sorted(i for b in kal.kosze(p, 300) for i in b), sorted(p))


class BramkaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.zestaw, self.odcinek = Path(self.tmp, "zestaw"), Path(self.tmp, "bridge-out")
        zapisz_logi(self.zestaw, PARTIE)
        self.odcinek.mkdir()
        (self.odcinek / "moves.jsonl").write_text("\n".join(json.dumps(w) for w in zagraj(99)), encoding="utf-8")
        (self.odcinek / "pomiar.json").write_text(json.dumps({"koniec": "przegrana", "przyczyna": None}))

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def bramka(self):
        return kal.bramka(ROOT, self.odcinek, self.zestaw)

    def test_zgodny_zestaw_i_zdrowy_most_przechodza(self):
        b = self.bramka()
        self.assertTrue(b["ok"], b["powody"])

    def test_zestaw_poza_tolerancja_blokuje(self):
        shutil.rmtree(self.zestaw)
        zapisz_logi(self.zestaw, [zagraj(s, 1.4) for s in range(1, 13)])
        self.assertIn("zestaw kontrolny poza tolerancją albo bez danych", self.bramka()["powody"])

    def test_pusty_zestaw_blokuje(self):
        shutil.rmtree(self.zestaw)
        self.assertIn("pusty zestaw kontrolny", self.bramka()["powody"])

    def test_most_z_awaria_blokuje_a_limit_ruchow_jest_zdrowy(self):
        (self.odcinek / "pomiar.json").write_text(json.dumps({"koniec": "awaria", "przyczyna": "CalledProcessError"}))
        self.assertFalse(self.bramka()["ok"])
        (self.odcinek / "pomiar.json").write_text(json.dumps({"koniec": "przerwanie", "przyczyna": "limit ruchów"}))
        self.assertTrue(self.bramka()["ok"])
        (self.odcinek / "pomiar.json").write_text(json.dumps({"koniec": "przerwanie", "przyczyna": "gra nie jest na pierwszym planie"}))
        self.assertFalse(self.bramka()["ok"])

    def test_krotki_odcinek_bez_danych_nie_blokuje_ale_zly_blokuje(self):
        (self.odcinek / "moves.jsonl").write_text("\n".join(json.dumps(w) for w in zagraj(5)[:6]), encoding="utf-8")
        self.assertTrue(self.bramka()["ok"])
        (self.odcinek / "moves.jsonl").write_text("\n".join(json.dumps(w) for w in zagraj(5, 1.5)), encoding="utf-8")
        # jedna krótka partia z licznikiem o 50% za wysokim ma za mało par tylko wtedy, gdy jest krótka
        b = self.bramka()
        self.assertEqual(b["ok"], b["odcinek"]["tempo"]["ok"] is not False)


class WyzwalaczTest(unittest.TestCase):
    def run_(self, ustaw, rozjazd_ok=True, proba=1):
        with tempfile.TemporaryDirectory() as d:
            ustaw(d)
            return kal.wyzwalacz(d, {"ok": rozjazd_ok}, proba)

    def wszystkie_wazne(self, d):
        for k in range(1, 11):
            pomiar(d, k, "przegrana" if k % 2 else "cel")

    def test_czysta_seria_bez_rozjazdu_nic_nie_robi(self):
        self.assertEqual(self.run_(self.wszystkie_wazne), "brak")

    def test_rozjazd_otwiera_utrzymanie(self):
        self.assertEqual(self.run_(self.wszystkie_wazne, rozjazd_ok=False), "utrzymanie rozjazd")

    def test_awaria_infrastruktury_to_ponowienie_bez_agenta(self):
        def ustaw(d):
            self.wszystkie_wazne(d)
            pomiar(d, 3, "awaria", "brak pomiar.json")
            shutil.rmtree(Path(d) / "seria-x-partia-3")
            (Path(d) / "seria-x-partia-3").mkdir()
            pomiar(d, 7, "awaria", "CalledProcessError: adb: device offline")
        self.assertEqual(self.run_(ustaw), "ponow [3, 7]")

    def test_po_limicie_ponowien_infrastruktura_otwiera_utrzymanie(self):
        def ustaw(d):
            self.wszystkie_wazne(d)
            pomiar(d, 3, "awaria", "adb: device offline")
        self.assertEqual(self.run_(ustaw, proba=K["ponowienia"]), "utrzymanie most")

    def test_seria_bez_zadnej_partii_to_ponowienie_calosci(self):
        self.assertEqual(self.run_(lambda d: None), "ponow " + json.dumps(list(range(1, 11))))

    def test_przerwanie_mostu_otwiera_utrzymanie_od_razu(self):
        def ustaw(d):
            self.wszystkie_wazne(d)
            pomiar(d, 2, "przerwanie", "gra nie jest na pierwszym planie")
        self.assertEqual(self.run_(ustaw), "utrzymanie most")

    def test_przerwanie_ma_pierwszenstwo_przed_rozjazdem(self):
        def ustaw(d):
            self.wszystkie_wazne(d)
            pomiar(d, 2, "awaria", "ValueError: odczyt")
        self.assertEqual(self.run_(ustaw, rozjazd_ok=False), "utrzymanie most")


class ZestawTest(unittest.TestCase):
    def test_zwarty_zapis_jest_deterministyczny_i_ucina_dlugie_partie(self):
        dlugie = [dict(w, drag={"finger": [1, 2]}, expected=[[0]], observed=[[0]], ok=True) for w in zagraj(3)]
        dlugie = (dlugie * 20)[:K["zestaw_ruchy"] + 50]
        with tempfile.TemporaryDirectory() as d:
            zapisz_logi(Path(d) / "s", [dlugie])
            kal.zapisz_zestaw(Path(d) / "s", "x", Path(d) / "a", K)
            kal.zapisz_zestaw(Path(d) / "s", "x", Path(d) / "b", K)
            plik = Path(d) / "a" / "x-1.jsonl.gz"
            self.assertEqual(plik.read_bytes(), (Path(d) / "b" / "x-1.jsonl.gz").read_bytes())
            wpisy = kal.wczytaj(plik)
            self.assertEqual(len(wpisy), K["zestaw_ruchy"])
            self.assertEqual(set(wpisy[0]) - {"move"}, {"n", "board", "tray", "score"})
            self.assertEqual(kal.logi(Path(d) / "a"), [wpisy])


class HashISciezkiTest(unittest.TestCase):
    def test_naprawa_mostu_zmienia_tylko_hash_mostu_a_symulatora_tylko_symulatora(self):
        with tempfile.TemporaryDirectory() as tmp:
            for grupa in CFG["tylko_do_odczytu"].values():
                for rel in grupa:
                    (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / rel, Path(tmp) / rel)
            for rel in (kal.ocena.OCENA_PY, kal.ocena.SERIA_YML):
                (Path(tmp) / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / rel, Path(tmp) / rel)
            h0 = kal.hashe(tmp)
            (Path(tmp) / "bridge.py").write_text("# naprawa mostu")
            h1 = kal.hashe(tmp)
            self.assertEqual(h1["sym"], h0["sym"])
            self.assertNotEqual(h1["most"], h0["most"])
            (Path(tmp) / "scoring.py").write_text("# kalibracja punktacji")
            h2 = kal.hashe(tmp)
            self.assertEqual(h2["most"], h1["most"])
            self.assertNotEqual(h2["sym"], h1["sym"])

    def test_dozwolone_tylko_pliki_ewaluatora_i_ich_testy(self):
        self.assertEqual(kal.dozwolone(["bridge.py", "game.py", "tools/bridge.sh", "tests/test_engine.py"]), [])
        self.assertEqual(kal.dozwolone(["bridge.py", ".github/workflows/seria.yml", ".github/evaluator/kalibracja.py",
                                        ".github/evaluator/kalibracja/zestaw/x.jsonl.gz", "policies.py"]),
                         [".github/workflows/seria.yml", ".github/evaluator/kalibracja.py",
                          ".github/evaluator/kalibracja/zestaw/x.jsonl.gz", "policies.py"])


class PolecenieTest(unittest.TestCase):
    def test_rozjazd_kod_wyjscia_i_zapis(self):
        with tempfile.TemporaryDirectory() as d:
            zapisz_logi(d + "/seria", PARTIE)
            run = lambda: subprocess.run([sys.executable, str(ROOT / ".github/evaluator/kalibracja.py"), "rozjazd",
                                          "--seria", d + "/seria", "--out", d + "/r.json"], capture_output=True, text=True)
            r = run()
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(json.loads(Path(d, "r.json").read_text())["ok"])
            shutil.rmtree(d + "/seria")
            zapisz_logi(d + "/seria", [zagraj(s, 1.5) for s in range(1, 13)])
            self.assertEqual(run().returncode, 1)

    def test_dozwolone_ze_standardowego_wejscia(self):
        run = lambda stdin: subprocess.run([sys.executable, str(ROOT / ".github/evaluator/kalibracja.py"), "dozwolone"],
                                           input=stdin, capture_output=True, text=True)
        self.assertEqual(run("bridge.py\ngame.py\n").returncode, 0)
        r = run("bridge.py\n.github/workflows/x.yml\n")
        self.assertEqual((r.returncode, r.stdout.strip()), (1, ".github/workflows/x.yml"))


if __name__ == "__main__":
    unittest.main()
