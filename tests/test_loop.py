"""Testy czystej logiki pętli (#16): raport, profile, przyczyna maszynowa, sekcje issue.

Wywołania `gh` i przebiegi Actions sprawdza dopiero bieg na sucho (#19).
"""
import importlib.util
import json
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("loop", os.path.join(ROOT, ".github", "loop", "loop.py"))
loop = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loop)

REPORT = loop.MARK + "\n```yaml\nstatus: done\ncommit: 9f3c1ab\n```\nProza.\n\n## Co dalej\n- nic\n"


class RaportTest(unittest.TestCase):
    def test_fields_czyta_skalary(self):
        self.assertEqual(loop.fields(REPORT), {"status": "done", "commit": "9f3c1ab"})

    def test_fields_obcina_komentarz_w_linii(self):
        self.assertEqual(loop.fields("```yaml\nreward_shape_changed: yes   # albo no\n```")["reward_shape_changed"], "yes")

    def test_set_fields_nadpisuje_dopisuje_i_kasuje(self):
        b = loop.set_fields(REPORT, {"status": "partial", "proby": 2, "commit": None})
        self.assertEqual(loop.fields(b), {"status": "partial", "proby": "2"})
        self.assertIn("## Co dalej", b)
        self.assertTrue(b.startswith(loop.MARK))

    def test_set_fields_zaklada_blok_gdy_brak(self):
        b = loop.set_fields("Sama proza.\n", {"status": "crashed"})
        self.assertEqual(loop.fields(b), {"status": "crashed"})
        self.assertIn("Sama proza.", b)

    def test_section_wycina_do_nastepnej(self):
        body = "## Cel\nx\n\n## Weryfikacja\n`python -m unittest`\n\n## Kontekst\ny\n"
        self.assertEqual(loop.section(body, "Weryfikacja"), "`python -m unittest`")
        self.assertEqual(loop.section(body, "Budżet"), "")

    def test_zaufanie_do_autora(self):
        self.assertTrue(loop.trusted({"author_association": "OWNER", "user": {"login": "x"}}))
        self.assertTrue(loop.trusted({"author_association": "NONE", "user": {"login": "github-actions[bot]"}}))
        self.assertFalse(loop.trusted({"author_association": "NONE", "user": {"login": "obcy"}}))
        self.assertFalse(loop.trusted({"author_association": "CONTRIBUTOR", "user": {"login": "obcy"}}))


class ProfilTest(unittest.TestCase):
    def test_zakaz_1_internet_i_kod(self):
        self.assertIsNotNone(loop.check_profile("x", {"internet": True, "write": ["**"]}))
        self.assertIsNotNone(loop.check_profile("x", {"internet": True, "write": ["docs/research/**", "bench/x.json"]}))
        self.assertIsNone(loop.check_profile("x", {"internet": True, "write": ["docs/research/**"]}))
        self.assertIsNone(loop.check_profile("x", {"internet": False, "write": ["**"]}))

    def test_profile_repo_nie_lamia_zakazu(self):
        import yaml
        with open(os.path.join(ROOT, ".claude", "profiles.yml"), encoding="utf-8") as fh:
            profiles = yaml.safe_load(fh)
        for role, p in profiles.items():
            self.assertIsNone(loop.check_profile(role, p), role)


class PrzyczynaTest(unittest.TestCase):
    def cause(self, payload, exit_code="0"):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            fh.write(payload if isinstance(payload, str) else json.dumps(payload))
        try:
            return loop.machine_cause(fh.name, exit_code)
        finally:
            os.unlink(fh.name)

    def test_auth_401_mimo_subtype_success(self):
        c, limited, _ = self.cause({"subtype": "success", "is_error": True, "api_error_status": 401, "terminal_reason": "api_error"})
        self.assertEqual(c, "api_error_status=401 terminal_reason=api_error")
        self.assertFalse(limited)

    def test_limit_subskrypcji(self):
        _, limited, _ = self.cause({"is_error": True, "result": "You've hit your session limit"})
        self.assertTrue(limited)

    def test_termin_resetu_w_sekundach_i_milisekundach(self):
        _, _, r1 = self.cause('{"resetsAt": 1790000000}')
        _, _, r2 = self.cause('{"resets_at": 1790000000000}')
        self.assertEqual(r1, r2)

    def test_termin_resetu_z_tekstu_cli(self):
        ref = loop.parse_time("2026-09-26T06:24:22Z")
        self.assertEqual(loop.text_reset("You've hit your session limit · resets 7:20am (UTC)", ref),
                         loop.parse_time("2026-09-26T07:20:00Z"))
        self.assertEqual(loop.text_reset("resets 5am (UTC)", ref), loop.parse_time("2026-09-27T05:00:00Z"))
        self.assertEqual(loop.text_reset("resets 3pm (Europe/Warsaw)", ref), loop.parse_time("2026-09-26T13:00:00Z"))
        self.assertEqual(loop.text_reset("resets Oct 2, 5am (UTC)", ref), loop.parse_time("2026-10-02T05:00:00Z"))
        self.assertIsNone(loop.text_reset("brak terminu", ref))

    def test_limit_z_terminem_w_tekscie(self):
        _, limited, reset = self.cause({"is_error": True, "result": "You've hit your session limit · resets 11:59pm (UTC)"})
        self.assertTrue(limited)
        self.assertEqual((reset.hour, reset.minute), (23, 59))

    def test_zwykly_blad_zadania(self):
        c, limited, reset = self.cause({"is_error": False, "result": "ok"}, exit_code="124")
        self.assertEqual((c, limited, reset), ("exit=124", False, None))

    def test_brak_pliku(self):
        c, limited, _ = loop.machine_cause("/nie/ma/takiego.json", "1")
        self.assertIn("brak-pliku-wykonania", c)
        self.assertFalse(limited)


class RunIssueTest(unittest.TestCase):
    def test_run_issue_obcina_role(self):
        self.assertEqual(loop.run_issue("session #12 · implementer"), "session #12")
        self.assertEqual(loop.run_issue("session #12"), "session #12")

    def test_run_issue_nie_myli_12_z_123(self):
        self.assertNotEqual(loop.run_issue("session #123 · verifier"), "session #12")


class ResumeTest(unittest.TestCase):
    def setUp(self):
        self.saved = {k: getattr(loop, k) for k in ("find_report", "issue", "label_names", "launch", "time", "now", "gh")}
        self.slept, self.launched, self.dispatched = [], [], []
        loop.gh = lambda *a, **k: self.dispatched.append(a) or ""
        loop.now = lambda: loop.parse_time("2026-09-25T12:00:00Z")
        loop.time = type("T", (), {"sleep": staticmethod(self.slept.append)})
        loop.issue = lambda n: {}
        loop.label_names = lambda i: {"blocked:rate-limit"}
        loop.launch = lambda n: self.launched.append(n) or True

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(loop, k, v)

    def report(self, due):
        body = "%s\n```yaml\nwznow_po: %s\n```\n" % (loop.MARK, due)
        loop.find_report = lambda n: {"body": body}

    def test_spi_do_terminu_i_wznawia(self):
        self.report("2026-09-25T12:30:00Z")
        loop.resume(58)
        self.assertEqual(self.slept, [1800])
        self.assertEqual(self.launched, [58])

    def test_termin_poza_limitem_joba_przekazuje_zegar(self):
        self.report("2026-09-26T12:00:00Z")
        loop.resume(58)
        self.assertEqual((self.slept, self.launched), ([loop.MAX_SLEEP_S], []))
        self.assertEqual(self.dispatched, [("workflow", "run", "resume.yml", "-f", "issue=58")])

    def test_zegar_nie_idzie_dalej_gdy_park_zdjety(self):
        self.report("2026-09-26T12:00:00Z")
        loop.label_names = lambda i: set()
        loop.resume(58)
        self.assertEqual(self.dispatched, [])

    def test_nie_wznawia_gdy_park_ma_nowy_termin(self):
        self.report("2026-09-25T12:30:00Z")
        slept = self.slept.append
        loop.time = type("T", (), {"sleep": staticmethod(lambda s: slept(s) or self.report("2026-09-25T16:00:00Z"))})
        loop.resume(58)
        self.assertEqual(self.launched, [])

    def test_nie_wznawia_gdy_park_zdjety(self):
        self.report("2026-09-25T11:00:00Z")
        loop.label_names = lambda i: set()
        loop.resume(58)
        self.assertEqual(self.launched, [])


class ZobowiazaniaTest(unittest.TestCase):
    """Epilog pyta o resztę pętli, gdy jego własny przebieg jeszcze trwa: nie może go liczyć jako zobowiązania."""
    def setUp(self):
        self.saved = {k: getattr(loop, k) for k in ("gh", "loop_open", "now")}
        self.env = os.environ.get("GITHUB_RUN_ID")
        os.environ["GITHUB_RUN_ID"] = "7"
        loop.now = lambda: loop.parse_time("2026-09-25T12:00:00Z")
        loop.loop_open = lambda: []
        loop.LAUNCHED.clear()

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(loop, k, v)
        loop.LAUNCHED.clear()
        if self.env is None:
            os.environ.pop("GITHUB_RUN_ID")
        else:
            os.environ["GITHUB_RUN_ID"] = self.env

    def runs(self, *runs):
        loop.gh = lambda *a, **k: json.dumps([dict(databaseId=i, displayTitle="session #%s" % i, status=s,
                                                   createdAt="2026-09-25T11:00:00Z") for i, s in runs])

    def test_wlasny_przebieg_to_nie_zobowiazanie(self):
        self.runs((7, "in_progress"))
        self.assertFalse(loop.commitments())

    def test_cudzy_przebieg_to_zobowiazanie(self):
        self.runs((7, "in_progress"), (8, "queued"))
        self.assertTrue(loop.commitments())

    def test_swiezy_dispatch_z_procesu_to_zobowiazanie(self):
        self.runs()
        loop.LAUNCHED.add(12)
        self.assertTrue(loop.commitments())


class BenchTest(unittest.TestCase):
    """Bramka „policzono" (#99) i wynik, który przeżywa pad po pomiarze (#90), na prawdziwym repo git."""
    def setUp(self):
        self.saved = {k: getattr(loop, k) for k in ("issue",)}
        self.work = tempfile.mkdtemp()
        self.tmp = tempfile.mkdtemp()
        self.env = os.environ.get("RUNNER_TEMP")
        os.environ["RUNNER_TEMP"] = self.tmp
        for args in (("init", "-q"), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
            loop.git(self.work, *args)
        os.makedirs(os.path.join(self.work, "bench"))
        with open(os.path.join(self.work, "bench", "record.json"), "w") as fh:
            fh.write("{}")
        loop.git(self.work, "add", "-A")
        loop.git(self.work, "commit", "-q", "-m", "start")

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(loop, k, v)
        if self.env is None:
            os.environ.pop("RUNNER_TEMP")
        else:
            os.environ["RUNNER_TEMP"] = self.env

    def run_bench(self, *cmds):
        loop.issue = lambda n: {"body": "## Weryfikacja\n\n" + "".join("```bash\n%s\n```\n" % c for c in cmds)}
        loop.bench(97, self.work)
        with open(os.path.join(self.tmp, "agent-exit")) as fh:
            return fh.read()

    def committed(self, path):
        return loop.git(self.work, "ls-files", "--error-unmatch", path, check=False).returncode == 0

    def test_wynik_scommitowany_przez_polecenie_to_policzono(self):
        self.assertEqual(self.run_bench("echo 1 > bench/97.json && git add -A bench && git commit -qm wynik"), "0")

    def test_wynik_w_katalogu_to_policzono_i_trafia_do_commita(self):
        self.assertEqual(self.run_bench("echo 1 > bench/97.json"), "0")
        self.assertTrue(self.committed("bench/97.json"))

    def test_nic_nie_policzono(self):
        self.assertEqual(self.run_bench("true"), "1")

    def test_pad_po_pomiarze_nie_gubi_wyniku(self):
        self.assertEqual(self.run_bench("echo 1 > bench/97.json", "false"), "1")
        self.assertTrue(self.committed("bench/97.json"))


class KrawedzTest(unittest.TestCase):
    """#114: krawędź blokowania zwalnia konsumenta tylko po `done`."""
    def setUp(self):
        self.saved = {k: getattr(loop, k) for k in ("update_report", "edit_labels", "spawn_successor", "gh", "api_list", "launch")}
        self.launched, self.closed = [], []
        self.edges = {}
        loop.update_report = lambda n, upd, prose="": self.closed.append((n, upd["status"])) or ""
        loop.edit_labels = lambda *a, **k: None
        loop.spawn_successor = lambda n, i, body: None
        loop.gh = lambda *a, **k: ""
        loop.api_list = lambda path: self.edges.get(int(path.split("/issues/")[1].split("/")[0]), [])
        loop.launch = lambda n: self.launched.append(n)

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(loop, k, v)

    def dep(self, n, role):
        return {"number": n, "state": "open", "labels": [{"name": "rola:" + role}]}

    def test_done_zwalnia_konsumenta(self):
        self.edges = {104: [self.dep(105, "bench")]}
        loop.close_out(104, {}, "done", {}, "")
        self.assertEqual(self.launched, [105])

    def test_crashed_zamyka_konsumentow_kaskada_a_orchestrator_rusza(self):
        self.edges = {104: [self.dep(105, "bench")], 105: [self.dep(107, "orchestrator")]}
        loop.close_out(104, {}, "crashed", {}, "")
        self.assertEqual(self.closed, [(104, "crashed"), (105, "blocked")])
        self.assertEqual(self.launched, [107])

    def test_partial_z_nastepca_nie_rusza_konsumentow(self):
        self.edges = {104: [self.dep(105, "bench")]}
        loop.spawn_successor = lambda n, i, body: 120
        loop.close_out(104, {}, "partial", {}, "")
        self.assertEqual(self.closed, [(104, "partial")])
        self.assertEqual(self.launched, [120])


if __name__ == "__main__":
    unittest.main()


class PoleWidzeniaTest(unittest.TestCase):
    """#65: pętla nie dotyka issues bez etykiety `loop:iteration N`."""

    def test_loop_open_pomija_issues_bez_roli_i_pr(self):
        def lab(*names):
            return [{"name": n} for n in names]
        issues = [{"number": 1, "labels": lab("wayfinder:map")},
                  {"number": 2, "labels": lab("rola:implementer", "loop:iteration 3")},
                  {"number": 3, "labels": lab("ready")},
                  {"number": 4, "labels": lab("rola:researcher"), "pull_request": {}},
                  {"number": 5, "labels": []}]
        orig = loop.api_list
        loop.api_list = lambda path: issues
        try:
            self.assertEqual([x["number"] for x in loop.loop_open()], [2])
        finally:
            loop.api_list = orig

    def test_resolve_odrzuca_issue_bez_petli_albo_roli(self):
        orig = loop.issue
        try:
            for labels in ([], [{"name": "ready"}], [{"name": "rola:implementer"}, {"name": "rola:researcher"}],
                           [{"name": "rola:implementer"}], [{"name": "loop:iteration 3"}]):
                loop.issue = lambda n, l=labels: {"state": "open", "labels": l, "body": ""}
                with self.assertRaises(SystemExit):
                    loop.resolve(1)
        finally:
            loop.issue = orig

    def test_dispatch_na_labeled_tylko_dla_ready(self):
        with open(os.path.join(ROOT, ".github", "workflows", "dispatch.yml"), encoding="utf-8") as fh:
            yml = fh.read()
        self.assertIn("github.event.label.name == 'ready'", yml)


class ZapisCykluTest(unittest.TestCase):
    """#66: sesja niedokończona scala dziennik i raport, nigdy kod."""

    def test_notes_only_przepuszcza_tylko_dziennik_i_raport(self):
        got = loop.notes_only(["docs/journal/cykl-0003.md", "RAPORT.md", "engine.py", "docs/inne.md", ".github/loop/loop.py"])
        self.assertEqual(got, ["docs/journal/cykl-0003.md", "RAPORT.md"])

    def test_merge_notes_scala_dziennik_bez_kodu(self):
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            def run(cwd, *a):
                subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, check=True, capture_output=True)
            origin, work = os.path.join(tmp, "o"), os.path.join(tmp, "w")
            os.mkdir(origin)
            run(origin, "init", "-q", "--bare", "-b", "main")
            run(tmp, "clone", "-q", origin, work)
            with open(os.path.join(work, "a.py"), "w") as fh:
                fh.write("1\n")
            run(work, "add", "-A")
            run(work, "commit", "-q", "-m", "init")
            run(work, "push", "-q", "origin", "HEAD:refs/heads/main")
            run(work, "checkout", "-q", "-b", "task/1")
            os.makedirs(os.path.join(work, "docs", "journal"))
            for name in ("docs/journal/cykl-0009.md", "a.py"):
                with open(os.path.join(work, name), "w") as fh:
                    fh.write("nowe\n")
            run(work, "add", "-A")
            run(work, "commit", "-q", "-m", "praca")
            os.environ.pop("DEFAULT_BRANCH", None)
            self.assertTrue(loop.merge_notes(work))
            files = subprocess.run(["git", "ls-tree", "-r", "--name-only", "main"], cwd=origin, capture_output=True, text=True).stdout.split()
            show = subprocess.run(["git", "show", "main:a.py"], cwd=origin, capture_output=True, text=True).stdout
            self.assertIn("docs/journal/cykl-0009.md", files)
            self.assertEqual(show, "1\n")
