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

class TestOfficialSourceDiscovery(unittest.TestCase):
    def test_govuk_search_api_returns_only_official_document_links(self):
        payload={"results":[
            {"title":"British government statement on Iran missile attacks",
             "link":"/government/news/iran-missile-statement","public_timestamp":"2026-10-28T07:00:00Z"},
            {"title":"Spoofed government report",
             "link":"https://gov.uk.attacker.org/misleading-report"},
            {"title":"Another official statement","link":"/government/news/another-statement"}]}
        with patch.object(cv,"fetch_bytes",return_value=(json.dumps(payload).encode(),"application/json")):
            links=cv.govuk_official_search("Iran missile attacks")
        self.assertEqual(len(links),2)
        self.assertEqual(links[0]["origin"],"govuk_official_search")
        self.assertTrue(all(link["url"].startswith("https://www.gov.uk/") for link in links))
    def test_issuer_search_limited_and_targeted(self):
        oil=cv.targeted_search_queries({"headline_claims":["Oil price tanker collision in Hormuz"]})
        evacuate=cv.targeted_search_queries({"headline_claims":["Embassy evacuation in Kuwait"]})
        self.assertEqual(len(oil),3)
        self.assertTrue(any("imo.org" in x for x in oil))
        self.assertTrue(any("mofa.gov.ae" in x for x in evacuate))
    def test_search_provider_failure_is_not_false_news(self):
        item={"headline_claims":["Oil tanker attacked near Hormuz"]}
        primary={"sources":[]}
        with patch.object(cv,"govuk_official_search",side_effect=TimeoutError("down")), \
             patch.object(cv,"bing_rss_search",side_effect=TimeoutError("down")):
            output=cv.discover_documents(item,primary)
        self.assertEqual(output["search_status"],"unavailable")
        self.assertEqual(output["official_documents_fetched"],0)
        self.assertTrue(output["errors"])

class TestEvidence(unittest.TestCase):
    def sample(self):
        return [{"event_id":"x","claim":"Military officials intercepted two missiles near port",
                 "discovery":{"documents":[{"id":"doc1","url":"https://www.centcom.mil/statement",
                   "title":"US CENTCOM statement","published_at_from_document":"2026-10-28",
                   "retrieved_at":"2026-10-28T12:00:00Z",
                   "passages":["Military officials said they intercepted two missiles near the port."]}]}}]
    def test_old_official_statement_cannot_support_newly_reported_incident(self):
        case=self.sample()
        case[0]["news_day"]="2026-10-28"
        case[0]["discovery"]["documents"][0]["published_at_from_document"]="Sept. 8, 2026"
        self.assertTrue(cv.source_precedes_claim_by_weeks("Sept. 8, 2026","2026-10-28"))
        self.assertFalse(cv.source_precedes_claim_by_weeks("Oct. 25, 2026","2026-10-28"))
        result=cv.validate_matches({"results":[{"event_id":"x","matches":[{
            "doc_id":"doc1","passage_index":0,"relation":"direct_statement",
            "quote":"they intercepted two missiles near the port"}]}]},case)
        verified=result["x"]["matches"][0]
        self.assertEqual(verified["relation"],"related_only")
        self.assertTrue(verified["older_document_than_claim"])
        self.assertFalse(verified["claim_validated_as_fact"])
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

class TestObservedFalseMatches(unittest.TestCase):
    def test_intention_to_target_is_not_proof_of_completed_us_strikes(self):
        match={"relation":"direct_statement",
               "source_url":"https://www.gov.uk/foreign-travel-advice/saudi-arabia",
               "source_date":None,
               "exact_quote":"Iran has stated its intention to target locations associated with the US and Israel"}
        self.assertIsNotNone(cv.check_specific_support(
            "Live Updates: War returns to Iran with Israel, US strikes",match))
    def test_houthi_launches_are_not_saudi_interceptions(self):
        match={"relation":"direct_statement",
               "source_url":"https://www.gov.uk/foreign-travel-advice/saudi-arabia",
               "source_date":None,
               "exact_quote":"the Houthis have launched missiles and drones targeting several locations in Saudi Arabia"}
        self.assertIsNotNone(cv.check_specific_support(
            "Regional tensions escalate as Saudi Arabia intercepts missiles, Iran warns US",match))
    def test_repair_already_published_false_matches(self):
        events={"events":[{"id":"a","headline_claims":[
            "Live Updates: War returns to Iran with Israel, US strikes"]}]}
        records={"a":{"research_status":"official_statement_located",
            "summary_nl":"Eerdere AI noemde dit bevestigd",
            "official_matches":[{
                "relation":"direct_statement",
                "source_url":"https://www.gov.uk/foreign-travel-advice/saudi-arabia",
                "source_date":None,
                "exact_quote":"Iran has stated its intention to target locations associated with the US and Israel"}]}}
        corrected=cv.recheck_saved_records(records,events)
        self.assertEqual(corrected,1)
        self.assertEqual(records["a"]["research_status"],"related_official_material")
        self.assertEqual(records["a"]["official_matches"][0]["relation"],"related_only")
        self.assertFalse(records["a"]["verified_event"])
        self.assertIn("geen specifieke bevestiging",records["a"]["summary_nl"])
    def test_specific_dated_original_statement_not_rejected_on_matching_action(self):
        match={"relation":"direct_statement",
               "source_url":"https://www.centcom.mil/MEDIA/PUBLIC-RELEASES/Article/123/example",
               "source_date":"Oct. 28, 2026",
               "exact_quote":"U.S. forces intercepted incoming missiles near the site."}
        self.assertIsNone(cv.check_specific_support(
            "U.S. forces intercepted incoming missiles near the site",match))

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
