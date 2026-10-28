"""Offline tests for original-publication verification. No network or API cost."""
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import claim_verify as cv

class TestSourceSafety(unittest.TestCase):
    def test_official_exact_allowlist(self):
        self.assertTrue(cv.is_official_url("https://www.centcom.mil/MEDIA/press-release.html"))
        self.assertTrue(cv.is_official_url("https://www.gov.uk/foreign-travel-advice/iran"))
        self.assertFalse(cv.is_official_url("https://centcom.mil.attacker.example/fake"))
        self.assertFalse(cv.is_official_url("http://centcom.mil/not-https"))
        self.assertFalse(cv.is_official_url("https://example.org/lie"))
        self.assertFalse(cv.is_official_url("https://www.centcom.mil/document.pdf"))
    def test_untrusted_rss_links_are_never_original_evidence(self):
        rss=b"""<?xml version="1.0"?><rss><channel>
          <item><title>Iran strike report</title><link>https://malicious.example/news</link></item>
          <item><title>US military statement</title><link>https://www.centcom.mil/MEDIA/press-release.html</link></item>
          </channel></rss>"""
        with patch.object(cv,"fetch_bytes",return_value=(rss,"application/rss+xml")):
            results=cv.bing_rss_search("iran attack")
        self.assertEqual(len(results),1)
        self.assertEqual(results[0]["url"],"https://www.centcom.mil/MEDIA/press-release.html")
    def test_not_a_source_when_page_has_no_matching_passage(self):
        html=b"<html><head><title>Official page</title></head><body><p>Administrative calendar schedule and health care office opening days.</p></body></html>"
        with patch.object(cv,"fetch_bytes",return_value=(html,"text/html")):
            with self.assertRaises(ValueError):
                cv.extract_official_document("https://www.centcom.mil/test","Iran launches missile strikes")

class TestEvidence(unittest.TestCase):
    def sample(self):
        return [{"event_id":"x","claim":"Iran launches missile strikes",
                 "discovery":{"documents":[{"id":"doc1","url":"https://www.centcom.mil/statement",
                   "title":"US CENTCOM statement","published_at_from_document":"2026-10-28",
                   "retrieved_at":"2026-10-28T12:00:00Z",
                   "passages":["Military officials said they intercepted two missiles near the port."]}]}}]
    def test_verbatim_quote_and_provenance(self):
        payload={"results":[{"event_id":"x","summary_nl":"Bron verklaart interceptie.",
                "matches":[{"doc_id":"doc1","passage_index":0,
                  "relation":"direct_statement","quote":"they intercepted two missiles near the port",
                  "explanation_nl":"Volgens de bron een interceptie"}]}]}
        out=cv.validate_matches(payload,self.sample())
        self.assertEqual(len(out["x"]["matches"]),1)
        m=out["x"]["matches"][0]
        self.assertEqual(m["source_url"],"https://www.centcom.mil/statement")
        self.assertFalse(m["claim_validated_as_fact"])
        self.assertEqual(m["source_date"],"2026-10-28")
    def test_fabricated_quote_and_unknown_document_rejected(self):
        payload={"results":[{"event_id":"x","matches":[
            {"doc_id":"doc1","passage_index":0,"relation":"direct_statement",
             "quote":"Iran launched 100 missiles, according to officials."},
            {"doc_id":"fabricated","passage_index":0,"relation":"direct_statement",
             "quote":"intercepted two missiles near the port"}]}]}
        out=cv.validate_matches(payload,self.sample())
        self.assertEqual(out["x"]["matches"],[])
    def test_contradiction_is_not_verified_event(self):
        payload={"results":[{"event_id":"x","matches":[
            {"doc_id":"doc1","passage_index":0,"relation":"conflicting_statement",
             "quote":"intercepted two missiles near the port"}]}]}
        out=cv.validate_matches(payload,self.sample())
        self.assertFalse(out["x"]["matches"][0]["claim_validated_as_fact"])

class TestLimits(unittest.TestCase):
    def test_daily_claim_limit_and_expiry(self):
        es={"events":[{"id":"a","editorial_importance":"high"},
                      {"id":"b","editorial_importance":"medium"},
                      {"id":"c","editorial_importance":"high"},
                      {"id":"d","editorial_importance":"high"}]}
        self.assertEqual(len(cv.choose_events(es,{},0)),3)
        self.assertEqual(len(cv.choose_events(es,{},8)),1)
        self.assertEqual(len(cv.choose_events(es,{},9)),0)
        self.assertEqual(len(cv.choose_events(es,{"a":{"checked_at":cv.now()}},0)),3)
        self.assertEqual([x["id"] for x in cv.choose_events(es,{"a":{"checked_at":cv.now()}},0)],["b","c","d"])
    def test_no_direct_claims_from_generic_source_index(self):
        primary={"sources":[{"status":"ok","links":[{"title":"Government home",
            "url":"https://www.gov.uk/"}]}]}
        self.assertEqual(cv.indexed_official_links("Iran missile strikes",primary),[])

if __name__=="__main__":
    unittest.main()
