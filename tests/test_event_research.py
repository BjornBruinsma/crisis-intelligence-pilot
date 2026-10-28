"""Offline tests for official-source collection and event grouping; no API keys."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import primary_sources as sources
import event_cluster as events

class TestOfficialSources(unittest.TestCase):
    def test_only_allowlisted_https_government_domains(self):
        self.assertTrue(sources.valid_official_url("https://www.gov.uk/foreign-travel-advice/iran"))
        self.assertFalse(sources.valid_official_url("https://www.gov.uk.attacker.com/fake"))
        self.assertFalse(sources.valid_official_url("http://www.gov.uk/page"))
        self.assertFalse(sources.valid_official_url("javascript:alert(1)"))
    def test_extracts_passages_and_links(self):
        record=("uk_iran","UK FCDO","https://www.gov.uk/foreign-travel-advice/iran","official_advisory")
        raw=b'<html><body><h1>Iran Travel Advice</h1><p>Officials warn that the security situation may result in travel disruption and the closure of airspace.</p><a href="/foreign-travel-advice/saudi-arabia">Saudi Arabia travel advisory and regional safety information</a></body></html>'
        d=sources.parse_document(record,raw)
        self.assertEqual(d["status"],"ok")
        self.assertTrue(any("airspace" in p for p in d["passages"]))
        self.assertTrue(d["links"][0]["url"].startswith("https://www.gov.uk/"))
    def test_rejects_unverified_feed_item_urls(self):
        record=("us_advisories","US State","https://travel.state.gov/_res/rss/TAsTWs.xml","official_rss")
        raw=b'<rss><channel><item><title>Iran Travel Advisory</title><link>https://attacker.example/advisory</link><pubDate>Wed, 28 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>'
        result=sources.parse_document(record,raw)
        self.assertEqual(len(result["links"]),0)

class TestClustering(unittest.TestCase):
    def setUp(self):
        self.claims=[
            {"id":"alpha","headline":"Saudi Arabia warns of travel disruptions",
             "editorial_importance":"high","source_urls":["https://example.com/1"]},
            {"id":"beta","headline":"Saudi Arabia travel disruption warning",
             "editorial_importance":"medium","source_urls":["https://example.com/2"]},
            {"id":"gamma","headline":"Oil prices decreased by one percent",
             "editorial_importance":"medium","source_urls":["https://example.com/3"]},
        ]
    def test_validate_strict_id_partition(self):
        parsed={"groups":[{"ids":["alpha","beta"],"label_nl":"Claim: travel warning"},
                          {"ids":["gamma"],"label_nl":"Claim: oil decreases"}]}
        g=events.validate_groups(parsed,self.claims)
        self.assertEqual([x["ids"] for x in g],[["alpha","beta"],["gamma"]])
        with self.assertRaises(ValueError):
            events.validate_groups({"groups":[{"ids":["alpha","gamma"]}]},self.claims)
        with self.assertRaises(ValueError):
            events.validate_groups({"groups":[{"ids":["alpha","alpha","beta","gamma"]}]},self.claims)
    def test_exact_official_excerpt_only(self):
        groups=[{"ids":["alpha"],"label_nl":"Claim: official evacuation"},
                {"ids":["beta","gamma"],"label_nl":"Claim: oil move"}]
        official=[{"id":"uk_saudi:p0","authority":"UK government",
                   "url":"https://www.gov.uk/foreign-travel-advice/saudi-arabia",
                   "text":"Officials warn that the airport may close at short notice.",
                   "type":"official_page_passage"}]
        model={"matches":[
            {"group_index":0,"evidence_id":"uk_saudi:p0",
             "relation":"supports_specific_claim",
             "exact_excerpt":"airport may close at short notice",
             "reason_nl":"The authority says so."},
            {"group_index":1,"evidence_id":"uk_saudi:p0",
             "relation":"supports_specific_claim",
             "exact_excerpt":"Saudi oil production officially halted",
             "reason_nl":"Fabricated evidence"}]}
        match=events.validate_matches(model,groups,official)
        self.assertEqual(len(match),1)
        self.assertTrue(match[0]["automatic_match_only"])
        result=events.build_events(groups,self.claims,match)
        self.assertTrue(all(x["verified_event"] is False for x in result))
        self.assertTrue(all(x["probability_estimate"] is None for x in result))
    def test_output_escapes_bad_headline(self):
        g=[{"ids":["alpha"],"label_nl":"Claim: <img src=x onerror=alert(1)>",
            "clustering_reason":"not validated"}]
        out=events.build_events(g,self.claims,{})
        content=events.render(out,{"status":"complete","last_attempt_utc":"now","model":"test"})
        self.assertIn("&lt;img",content)
        self.assertNotIn("<img src=x",content)
    def test_no_model_results_marks_unverified_candidates(self):
        fallback=events.fallback_groups(self.claims)
        groups=events.build_events(fallback,self.claims,{})
        self.assertEqual(len(groups),3)
        self.assertTrue(all(x["research_status"]=="no_matching_primary_evidence" for x in groups))

if __name__=="__main__":
    unittest.main()
