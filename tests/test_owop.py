import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("owop_editorial", ROOT / "scripts" / "owop_editorial.py")
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class OwopClusteringTests(unittest.TestCase):
    def test_normalized_strips_publisher_suffix(self):
        self.assertEqual(MOD.normalized("Turtles return to beach - Example News"), "turtles return to beach")

    def test_similar_headlines_cluster(self):
        a = "Sea turtle population returns after conservation project"
        b = "Sea turtle population returns after conservation project - News Site"
        self.assertGreaterEqual(MOD.sim(a, b), 0.72)

    def test_low_signal_is_filtered(self):
        groups = MOD.cluster_articles([{
            "title": "Celebrity red carpet good news",
            "published_at": "2026-10-27T10:00:00Z",
            "publisher": "x",
            "topic": [],
            "language": "en",
            "sourcecountry": "US",
            "url": "https://x.test/a"
        }])
        self.assertEqual(groups, [])


if __name__ == "__main__":
    unittest.main()
