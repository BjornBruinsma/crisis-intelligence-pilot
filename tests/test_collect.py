"""Offline tests for candidate news collection. Never require live APIs."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import collect


RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Search</title><item>
<title>Iran &amp; Gulf shipping - Test Publisher</title>
<link>https://news.google.com/rss/articles/test123</link>
<guid isPermaLink="false">test123</guid>
<pubDate>Mon, 26 Oct 2026 11:22:00 GMT</pubDate>
<source url="https://example.org">Test Publisher</source>
</item></channel></rss>"""


class TestCollect(unittest.TestCase):
    def test_profiles_are_complete(self):
        self.assertEqual(len(collect.PROFILES), 12)
        self.assertEqual(len({x[0] for x in collect.PROFILES}), 12)

    def test_rss_url_encoding(self):
        profile = collect.PROFILES[8]
        url = collect.rss_url(*profile[2:])
        self.assertIn("news.google.com/rss/search", url)
        self.assertIn("ceid=", url)
        self.assertIn("%D8", url)

    def test_rss_parse_and_escape(self):
        result = collect.parse_rss(RSS, collect.PROFILES[0], "2026-10-26T12:00:00Z")
        self.assertEqual(len(result), 1)
        record = result[0]
        self.assertEqual(record["title"], "Iran & Gulf shipping - Test Publisher")
        self.assertEqual(record["publisher"], "Test Publisher")
        self.assertEqual(record["review_status"], "unverified")
        self.assertEqual(record["provider"], "google_news_rss")
        self.assertEqual(record["published_at"], "2026-10-26T11:22:00Z")
        self.assertEqual(record["sourcecountry"], "")

    def test_dedupes_across_feed_profiles(self):
        a = collect.parse_rss(RSS, collect.PROFILES[0], "2026-10-26T12:00:00Z")
        b = collect.parse_rss(RSS, collect.PROFILES[1], "2026-10-26T12:01:00Z")
        merged, added = collect.merge_articles(a, b)
        self.assertEqual(len(merged), 1)
        self.assertEqual(added, 0)
        self.assertEqual(len(merged[0]["topic"]), 2)

    def test_gdelt_parser(self):
        payload = {"articles": [{
            "url": "https://example.com/news",
            "title": "Détente & talks",
            "seendate": "20261026T115900Z",
            "domain": "example.com",
            "sourcecountry": "China",
        }]}
        records = collect.parse_gdelt(json.dumps(payload).encode(), "gdelt-iran", "2026-10-26T12:00:00Z")
        self.assertEqual(records[0]["published_at"], "2026-10-26T11:59:00Z")
        self.assertEqual(records[0]["sourcecountry"], "China")

    def test_invalid_feed_reports_error(self):
        with self.assertRaises(ValueError):
            collect.parse_rss(b"<html>not RSS</html>", collect.PROFILES[0], "2026-10-26T12:00:00Z")

    def test_age_window(self):
        date = dt.datetime(2026, 10, 26, tzinfo=dt.timezone.utc)
        cutoff = date - dt.timedelta(days=45)
        self.assertTrue(collect.keep_recent({"first_seen": "2026-10-26T11:00:00Z"}, cutoff))
        self.assertFalse(collect.keep_recent({"first_seen": "2026-05-01T11:00:00Z"}, cutoff))


if __name__ == "__main__":
    unittest.main()
