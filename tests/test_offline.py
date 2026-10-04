"""Testy fazy offline: odtworzenie nagranego drzewa, wersje polityki, argmax, wdrożenie i to, co widzi sesja."""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, ".github", "loop"))
import drzewo  # noqa: E402
import loop  # noqa: E402
import offline  # noqa: E402

CFG = {"W": 4, "K": 7, "beta": 0.01, "M": 3}
BIEZACA = os.path.join(ROOT, drzewo.POLICY)
policy, DIGEST = drzewo.load_policy(ROOT)

WYJATEK = "def solve(q):\n    raise ValueError('zepsuta')\n"
PETLA = "def solve(q):\n    while True:\n        pass\n"
PUSTA = "def solve(q):\n    return []\n"


def rec(node, s, kol, minuty=60):
    chain, depth = node.split(".")
    parent = "%s.%d" % (chain, int(depth) - 1) if int(depth) > 1 else "korzen"
    return {"rodzic": parent, "rodzic_sha": "K", "kolejnosc": kol, "sha": "sha-" + node, "stan": "oceniony",
            "gist": "g", "notatki": ["tajna notatka"], "koszt": {"tury": 3, "usd": 1.0, "minuty": minuty},
            "oczekiwanie_min": 5.0, "kontynuacje_tur": 0, "sesje": [{"przyczyna": "ok"}],
            "oceny": {"s_sym": {"h": s}, "czas_sym_min": 0}}


def wynik_zywy(name):
    """Deterministyczny wynik węzła: łańcuch 1 rośnie, 2 stoi, 3 spada, 4 rośnie wolno."""
    c, d = (int(x) for x in name.split("."))
    return {1: 0.1 * d, 2: 0.05, 3: max(0.0, 0.2 - 0.1 * d), 4: 0.02 * d}[c]


def czytaj(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class Baza(unittest.TestCase):
    def setUp(self):
        self.base = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.base, True)
        os.makedirs(os.path.join(self.base, ".github", "policy"))
        loop.write_json(os.path.join(self.base, drzewo.CONFIG), CFG)
        shutil.copy(BIEZACA, os.path.join(self.base, drzewo.POLICY))
        shutil.copy(os.path.join(ROOT, offline.OPIS), os.path.join(self.base, offline.OPIS))

    def zywe_drzewo(self, t=1, wynik=wynik_zywy):
        """Prawdziwe kroki harmonogramu z polityką z repo aż do zamknięcia; zwraca polecenia zamykające."""
        pol, dig = drzewo.load_policy(self.base)
        while True:
            polecenia = drzewo.krok(self.base, t, pol, dig, CFG, False)
            wezly = [p for p in polecenia if p[0] == "WEZEL"]
            if not wezly:
                return polecenia
            for _, tree, n, kol in wezly:
                loop.write_json(loop.record_path(self.base, tree, n), rec(n, wynik(n), kol))


class OdtworzenieTest(Baza):
    def test_odtworzenie_bierzacej_polityki_daje_to_samo_co_zywe_drzewo(self):
        self.assertEqual(self.zywe_drzewo(), [("OFFLINE", 1)])
        st = drzewo.read_state(self.base, 1)
        w = offline.odtworz(policy, loop.load_tree(self.base, 1), CFG, 0.0)
        self.assertAlmostEqual(w["V"], st["koniec"]["V"], places=5)
        self.assertAlmostEqual(w["T_h"], st["koniec"]["T_h"], places=2)
        self.assertEqual(w["rundy"], len(st["paczki"]))
        self.assertEqual(w["ujawnione"], sum(len(p) for p in st["paczki"]))

    def test_wezel_spoza_nagrania_konczy_lancuch_bez_kary(self):
        class Pol:
            solve = staticmethod(lambda q: q.legal_actions()[1:] or [None])
        w = offline.odtworz(Pol, {"1.1": rec("1.1", 0.3, 1), "1.2": rec("1.2", 0.5, 2)}, CFG, 0.0)
        self.assertEqual(w["ujawnione"], 2)
        self.assertAlmostEqual(w["T_h"], 2.0)   # 1.3 nie istnieje: nie kosztuje
        self.assertAlmostEqual(w["V"], 0.5 - 0.01 * 2.0)
        self.assertTrue(any("poza nagraniem" in line for line in w["slad"]))

    def test_nowy_lancuch_bierze_najwczesniej_utworzony_nieuzyty_korzen(self):
        class Pol:
            solve = staticmethod(lambda q: [None] if q.round == 0 else [])
        w = offline.odtworz(Pol, {"1.1": rec("1.1", 0.2, 2), "3.1": rec("3.1", 0.9, 1)}, CFG, 0.0)
        self.assertAlmostEqual(w["najlepszy"], 0.9)

    def test_brak_korzeni_w_nagraniu_konczy_odtwarzanie_zamiast_krecic_sie(self):
        class Pol:
            solve = staticmethod(lambda q: [None])
        w = offline.odtworz(Pol, {"1.1": rec("1.1", 0.2, 1)}, CFG, 0.0)
        self.assertEqual((w["rundy"], w["powod"]), (1, "pusta paczka"))

    def test_runda_bez_ujawnienia_nie_liczy_sie_do_K(self):
        class Pol:
            solve = staticmethod(lambda q: [None, "1.1"] if q.round == 0 else [None])
        w = offline.odtworz(Pol, {"1.1": rec("1.1", 0.2, 1)}, dict(CFG, K=1), 0.0)
        self.assertEqual(w["rundy"], 1)

    def test_K_konczy_odtwarzanie(self):
        self.zywe_drzewo()
        w = offline.odtworz(policy, loop.load_tree(self.base, 1), dict(CFG, K=2), 0.0)
        self.assertEqual((w["rundy"], w["powod"]), (2, "K"))


class BezpieczneOdtworzenieTest(Baza):
    def setUp(self):
        super().setUp()
        self.zywe_drzewo()

    def plik(self, tekst):
        p = os.path.join(self.base, "kandydat.py")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(tekst)
        return p

    def test_bierzaca_polityka_przechodzi(self):
        w = offline.odtworz_bezpiecznie(self.base, BIEZACA)
        self.assertNotIn("blad", w)
        self.assertEqual(w["skrot"], DIGEST)
        self.assertEqual(list(w["drzewa"]), ["1"])

    def test_wyjatek_polityki_to_blad_wersji(self):
        self.assertIn("zepsuta", offline.odtworz_bezpiecznie(self.base, self.plik(WYJATEK))["blad"])

    def test_polityka_losowa_jest_odrzucona(self):
        w = offline.odtworz_bezpiecznie(self.base, self.plik(
            "import random\ndef solve(q):\n    return [None] * random.randint(0, 4)\n"))
        self.assertIn("nie jest deterministyczna", w["blad"])

    def test_petla_nieskonczona_to_blad_po_limicie(self):
        stary, offline.LIMIT_S = offline.LIMIT_S, 2
        self.addCleanup(setattr, offline, "LIMIT_S", stary)
        self.assertIn("dłużej", offline.odtworz_bezpiecznie(self.base, self.plik(PETLA))["blad"])

    def test_kandydat_nie_dostaje_sekretow_ze_srodowiska(self):
        os.environ["GH_TOKEN"] = "tajny"
        self.addCleanup(os.environ.pop, "GH_TOKEN", None)
        w = offline.odtworz_bezpiecznie(self.base, self.plik(
            "import os\ndef solve(q):\n    assert 'GH_TOKEN' not in os.environ\n    return []\n"))
        self.assertNotIn("blad", w)


class WyborTest(unittest.TestCase):
    def test_remis_zostawia_biezaca(self):
        self.assertEqual(offline.najlepsza({0: {"V": 0.5}, 1: {"V": 0.5}, 2: {"V": 0.5}}), 0)

    def test_wygrywa_najwyzsze_V_a_przy_remisie_wczesniejsza(self):
        self.assertEqual(offline.najlepsza({0: {"V": 0.5}, 1: {"V": 0.7}, 2: {"V": 0.7}, 3: {"V": 0.6}}), 1)

    def test_wersja_z_bledem_nie_wygrywa(self):
        self.assertEqual(offline.najlepsza({0: {"V": 0.5}, 1: {"V": None, "blad": "x"}}), 0)

    def test_nigdy_gorsza_od_biezacej(self):
        for vs in ([0.5, 0.1, 0.2], [0.5, None, 0.5], [0.5, 0.9, 0.1]):
            w = {i: {"V": v} for i, v in enumerate(vs)}
            self.assertGreaterEqual(w[offline.najlepsza(w)]["V"], vs[0])


class PrzebiegTest(Baza):
    """Cały przebieg bez agenta: sesję zastępuje podmiana pliku w katalogu meta."""

    def setUp(self):
        super().setUp()
        self.zywe_drzewo()
        self.run, self.meta = os.path.join(self.base, "run"), os.path.join(self.base, "meta")
        cwd = os.getcwd()
        os.chdir(self.base)
        self.addCleanup(os.chdir, cwd)
        self.polecenie("init", "1", self.run)

    def polecenie(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            kod = offline.main(["offline.py", *args])
        self.wyjscie = out.getvalue()
        return kod

    def sesja(self, m, tekst):
        self.polecenie("meta", str(m), self.run, self.meta)
        if tekst is not None:
            with open(os.path.join(self.meta, "policy.py"), "w", encoding="utf-8") as fh:
                fh.write(tekst)
        self.polecenie("wynik", str(m), self.run, self.meta)

    def test_katalog_sesji_ma_tylko_allowliste_bez_kodu_i_notatek(self):
        self.polecenie("meta", "1", self.run, self.meta)
        pliki = sorted(os.path.relpath(os.path.join(d, f), self.meta).replace(os.sep, "/")
                       for d, _, fs in os.walk(self.meta) for f in fs)
        self.assertEqual(pliki, ["ZADANIE.md", "baseline.json", "drzewa/1/manifest.json", "history/biezaca/r0000/policy.py",
                                 "history/biezaca/r0000/slady/1.txt", "history/biezaca/r0000/wynik.json",
                                 "konfiguracja.json", "policy.py"])
        tekst = " ".join(czytaj(os.path.join(d, f)) for d, _, fs in os.walk(self.meta) for f in fs)
        for zakazane in ("tajna notatka", "sha-1.1", "notatki", "gist"):
            self.assertNotIn(zakazane, tekst)

    def test_sesja_zaczyna_od_najlepszej_dotad_wersji(self):
        self.sesja(1, PUSTA)   # gorsza od bieżącej
        self.polecenie("meta", "2", self.run, self.meta)
        self.assertEqual(czytaj(os.path.join(self.meta, "policy.py")), czytaj(BIEZACA))
        self.assertTrue(os.path.isdir(os.path.join(self.meta, "history", "biezaca", "r0001")))

    def test_gorsza_wersja_nie_zastepuje_polityki_a_archiwum_zostaje(self):
        self.sesja(1, PUSTA)
        przed = czytaj(os.path.join(self.base, drzewo.POLICY))
        wyniki = offline.wczytaj_wyniki(self.run)
        self.assertLess(wyniki[1]["V"], wyniki[0]["V"])
        self.assertEqual(self.polecenie("wybierz", "1", self.run), 0)
        self.assertEqual(czytaj(os.path.join(self.base, drzewo.POLICY)), przed)
        arch = os.path.join(self.base, offline.HISTORIA, "faza-1")
        self.assertEqual(sorted(os.listdir(arch)), ["r0000", "r0001"])
        self.assertEqual(sorted(os.listdir(os.path.join(arch, "r0001"))), ["policy.py", "wynik.json"])

    def test_lepsza_wersja_zastepuje_polityke(self):
        # wszystkie łańcuchy płaskie: bieżąca polityka traci dwie rundy na nietrafienia, jedna runda wystarcza
        self.setUp_plaskie()
        jedna_runda = "def solve(q):\n    return [None] * q.max_parallelism if q.round == 0 else []\n"
        self.sesja(1, jedna_runda)
        w = offline.wczytaj_wyniki(self.run)
        self.assertGreater(w[1]["V"], w[0]["V"])
        self.polecenie("wybierz", "1", self.run)
        self.assertEqual(czytaj(os.path.join(self.base, drzewo.POLICY)), jedna_runda)

    def setUp_plaskie(self):
        shutil.rmtree(os.path.join(self.base, loop.TREES))
        self.zywe_drzewo(wynik=lambda n: 0.8)
        self.polecenie("init", "1", self.run)

    def test_sesja_z_bledem_i_bez_pliku_nie_wygrywa_i_nie_psuje_przebiegu(self):
        self.sesja(1, WYJATEK)
        self.polecenie("meta", "2", self.run, self.meta)
        os.remove(os.path.join(self.meta, "policy.py"))
        self.polecenie("wynik", "2", self.run, self.meta)
        w = offline.wczytaj_wyniki(self.run)
        self.assertIsNone(w[1]["V"])
        self.assertIn("brak policy.py", w[2]["blad"])
        self.polecenie("wybierz", "1", self.run)

    def test_podsumowanie_ma_tabele_czasow_postepu_i_zgodnosc_z_zywym(self):
        self.sesja(1, None)
        self.polecenie("wybierz", "1", self.run)
        for fragment in ("### Wersje polityki", "### Drzewo 1: postęp", "oczekiwanie min", "po turach / po limicie", "zgodne"):
            self.assertIn(fragment, self.wyjscie)
        self.assertNotIn("ROZBIEŻNE", self.wyjscie)


if __name__ == "__main__":
    unittest.main()
