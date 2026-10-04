"""Pętla `utrzymanie.sh` z atrapą claude i atrapą emulatora: status, łatka, pliki spoza dozwolonych, poświadczenie."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_kalibracja import K, PARTIE, ROOT, kal, zagraj, zapisz_logi  # noqa: E402  (tylko pomocnicy, nie klasy testów)


def znajdz_bash():
    """Na Windowsie `bash` z PATH bywa WSL-em; bierzemy bash z instalacji Gita."""
    git = shutil.which("git")
    if git:
        kandydat = Path(git).resolve().parents[1] / "bin" / "bash.exe"
        if kandydat.exists():
            return str(kandydat)
    return shutil.which("bash")


BASH = znajdz_bash()
ATRAPA_TESTU = "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        pass\n"


@unittest.skipUnless(BASH and shutil.which("git"), "brak bash/git")
class SkryptUtrzymaniaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        t = self.tmp
        self.zaufane, self.work, self.wynik, self.bin = t / "zaufane", t / "work", t / "wynik", t / "bin"
        shutil.copytree(ROOT / ".github", self.zaufane / ".github", ignore=shutil.ignore_patterns("__pycache__", "zestaw"))
        zapisz_logi(t / "logi", PARTIE)
        kal.zapisz_zestaw(t / "logi", "x", self.zaufane / ".github/evaluator/kalibracja/zestaw", K)
        for rel in kal.sciezki_naprawy() + ["policies.py"]:
            (self.work / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / rel, self.work / rel)
        for nazwa in ("test_engine", "test_bridge"):   # testy silnika mają własny przebieg, tu liczy się logika pętli
            (self.work / "tests" / (nazwa + ".py")).write_text(ATRAPA_TESTU, newline="\n")
        shutil.copyfile(ROOT / ".gitignore", self.work / ".gitignore")
        (self.work / ".zadanie").mkdir()
        # atrapa emulatora: gotowy odcinek zamiast gry
        self.most('mkdir -p bridge-out && cp "$STUB_ODCINEK"/* bridge-out/\n')
        self.odcinek = t / "odcinek"
        self.odcinek.mkdir()
        (self.odcinek / "moves.jsonl").write_text("\n".join(json.dumps(w) for w in zagraj(99)), encoding="utf-8")
        self.pomiar({"koniec": "przegrana", "przyczyna": None})
        self.bin.mkdir()
        (self.bin / "python3").write_text('#!/bin/bash\nexec "%s" "$@"\n' % Path(sys.executable).as_posix(), newline="\n")
        (self.bin / "claude").write_text('#!/bin/bash\ncd "$WORK" && eval "$STUB_AKCJA"\n', newline="\n")
        self.git = ["git", "-C", str(self.work)]
        self.ident = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
        subprocess.run(self.git + ["init", "-q"], check=True)
        (self.work / ".git" / "info" / "exclude").write_text(".zadanie/\nbridge-out/\n")
        subprocess.run(self.git + ["add", "-A"], check=True)
        subprocess.run(self.git + ["commit", "-q", "-m", "baza"], check=True, env=dict(os.environ, **self.ident))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def most(self, tresc):
        (self.work / "tools" / "bridge.sh").write_text(tresc, encoding="utf-8", newline="\n")

    def pomiar(self, obj):
        (self.odcinek / "pomiar.json").write_text(json.dumps(obj))

    def petla(self, akcja, iteracje=2):
        path = "%s%s%s" % (self.bin.as_posix(), os.pathsep, os.environ["PATH"])
        env = dict(os.environ, **self.ident, ZAUFANE=self.zaufane.as_posix(), WORK=self.work.as_posix(), WYNIK=self.wynik.as_posix(),
                   POWOD="rozjazd", ID="x", ITERACJE=str(iteracje), ITERACJA_MIN="1", STUB_AKCJA=akcja,
                   STUB_ODCINEK=self.odcinek.as_posix(), PATH=path, CLAUDE_CODE_OAUTH_TOKEN="tajne")
        r = subprocess.run([BASH, (ROOT / ".github/loop/utrzymanie.sh").as_posix(), "petla"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return ((self.wynik / "status").read_text().strip(), (self.wynik / "naprawa.patch").read_text(),
                (self.wynik / "iteracje.md").read_text(encoding="utf-8", errors="replace"))

    def test_naprawa_w_dozwolonych_plikach_przechodzi_w_pierwszej_iteracji(self):
        status, patch, _ = self.petla('echo "# poprawka" >> game.py && git add -A && git commit -qm poprawka')
        self.assertEqual(status, "przeszla")
        self.assertIn("game.py", patch)
        self.assertTrue((self.wynik / "iteracja-1" / "agent-exit").exists())
        self.assertFalse((self.wynik / "iteracja-2").exists())
        zadanie = (self.work / ".zadanie" / "ZADANIE.md").read_text(encoding="utf-8")
        self.assertIn("Powód: `rozjazd`", zadanie)
        self.assertIn("scoring.py", zadanie)

    def test_niezatwierdzone_zmiany_agenta_tez_wchodza(self):
        status, patch, _ = self.petla('echo "# poprawka" >> scoring.py')
        self.assertEqual(status, "przeszla")
        self.assertIn("scoring.py", patch)

    def test_zmiana_spoza_dozwolonych_nie_przechodzi_i_nie_wchodzi_do_lacki(self):
        status, patch, iteracje = self.petla('echo "# oszustwo" >> policies.py && echo "# poprawka" >> game.py')
        self.assertEqual(status, "nieudane")
        self.assertIn("policies.py", iteracje)
        self.assertIn("### Iteracja 2", iteracje)
        self.assertNotIn("policies.py", patch)
        self.assertIn("game.py", patch)

    def test_bramka_nie_do_przejscia_zostawia_nieudane_i_pusta_lacke(self):
        self.pomiar({"koniec": "awaria", "przyczyna": "adb"})
        status, patch, iteracje = self.petla("true")
        self.assertEqual((status, patch), ("nieudane", ""))
        self.assertIn("most: awaria", iteracje)

    def test_poprzednie_iteracje_trafiaja_do_zadania(self):
        self.pomiar({"koniec": "awaria", "przyczyna": "adb"})
        self.petla("true")
        zadanie = (self.work / ".zadanie" / "ZADANIE.md").read_text(encoding="utf-8")
        self.assertIn("Iteracja 2 z 2", zadanie)
        self.assertIn("### Iteracja 1", zadanie)

    def test_kod_naprawy_nie_widzi_poswiadczenia_w_sprawdzeniu(self):
        self.most('echo "[${CLAUDE_CODE_OAUTH_TOKEN:-brak}]" > "$STUB_ODCINEK/../widziane"\n'
                  'mkdir -p bridge-out && cp "$STUB_ODCINEK"/* bridge-out/\n')
        self.petla("true")
        self.assertEqual((self.tmp / "widziane").read_text().strip(), "[brak]")


if __name__ == "__main__":
    unittest.main()
