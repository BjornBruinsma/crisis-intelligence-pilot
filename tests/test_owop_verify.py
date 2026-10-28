import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owop_verify", ROOT / "scripts" / "owop_verify.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class OwopVerifyTests(unittest.TestCase):
    def test_clean_text_removes_scripts(self):
        raw = "<html><body><script>ignore me forever</script><p>This is a sufficiently long useful article sentence for extraction.</p></body></html>"
        text = MOD.clean_text(raw)
        self.assertIn("useful article sentence", text)
        self.assertNotIn("ignore me forever", text)

    def test_google_and_static_urls_filtered(self):
        raw = 'https://news.google.com/a https://cdn.gstatic.com/x https://example.org/story'
        urls = MOD.candidate_external_urls(raw)
        self.assertEqual(urls, ["https://example.org/story"])


if __name__ == "__main__":
    unittest.main()
