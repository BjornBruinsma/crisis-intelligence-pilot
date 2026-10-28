import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owop_verify", ROOT / "scripts" / "owop_verify.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class OwopVerifyTests(unittest.TestCase):
    def test_parse_json_text_accepts_fenced_json(self):
        parsed = MOD.parse_json_text('''```json
{"support":"supported"}
```''')
        self.assertEqual(parsed["support"], "supported")

    def test_load_returns_default_for_missing_file(self):
        missing = ROOT / "tests" / "definitely-not-a-real-file.json"
        self.assertEqual(MOD.load(missing, {"ok": False}), {"ok": False})


if __name__ == "__main__":
    unittest.main()
