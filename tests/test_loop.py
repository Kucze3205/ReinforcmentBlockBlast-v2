"""Testy czystej logiki klocków pętli: raport i przyczyna maszynowa."""
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

    def test_zaufanie_do_autora(self):
        self.assertTrue(loop.trusted({"author_association": "OWNER", "user": {"login": "x"}}))
        self.assertTrue(loop.trusted({"author_association": "NONE", "user": {"login": "github-actions[bot]"}}))
        self.assertFalse(loop.trusted({"author_association": "NONE", "user": {"login": "obcy"}}))
        self.assertFalse(loop.trusted({"author_association": "CONTRIBUTOR", "user": {"login": "obcy"}}))


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


if __name__ == "__main__":
    unittest.main()
