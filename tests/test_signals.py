"""Tests for non-predictive editorial signal indicators."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import signals

class TestSignalMonitor(unittest.TestCase):
    def sample(self):
        events={"status":"complete","events":[
            {"headline_claim_ids":["a","b"]},
            {"headline_claim_ids":["c"]},
            {"headline_claim_ids":["d"]},
            {"headline_claim_ids":["e"]}]}
        ai={"assessments":{
            "a":{"direction":"escalation"},"b":{"direction":"escalation"},
            "c":{"direction":"deescalation"},"d":{"direction":"escalation"},
            "e":{"direction":"neutral"}}}
        qa={"technical":{"ids_retained_without_duplicates":True,
                         "potential_direct_support_matches":0,
                         "official_sources_accessible":7,
                         "official_sources_checked":9}}
        return events,ai,qa
    def test_counts_groups_not_headlines(self):
        events,ai,qa=self.sample()
        data=signals.compute(events,ai,qa,now="2026-10-28T12:00:00Z")
        self.assertEqual(data["sample_size_groups"],4)
        self.assertEqual(data["news_direction_groups"]["escalation"],2)
        self.assertEqual(data["news_direction_groups"]["deescalation"],1)
        self.assertEqual(data["verified_event_count"],0)
        self.assertTrue(data["cannot_infer_probability"])
        self.assertTrue(data["complete"])
    def test_disagreeing_member_directions_are_mixed(self):
        events,ai,qa=self.sample()
        ai["assessments"]["b"]["direction"]="deescalation"
        data=signals.compute(events,ai,qa)
        self.assertEqual(data["news_direction_groups"]["mixed"],1)
        self.assertEqual(data["news_direction_groups"]["escalation"],1)
    def test_incomplete_research_not_marked_complete(self):
        events,ai,qa=self.sample()
        qa["technical"]["ids_retained_without_duplicates"]=False
        self.assertFalse(signals.compute(events,ai,qa)["complete"])
    def test_daily_snapshots_replace_same_day(self):
        events,ai,qa=self.sample()
        earlier=signals.compute(events,ai,qa,"2026-10-28T07:00:00Z")
        later=signals.compute(events,ai,qa,"2026-10-28T12:00:00Z")
        previous=signals.update_history([],earlier)
        updated=signals.update_history(previous,later)
        self.assertEqual(len(updated),1)
        self.assertEqual(updated[0]["day"],"2026-10-28")
        self.assertIn("NOT actual event frequency",updated[0]["note"])
    def test_page_warns_probabilities_are_not_available(self):
        data=signals.compute(*self.sample())
        page=signals.render(data,signals.update_history([],data))
        self.assertIn("géén voorspellingen",page)
        self.assertIn("geen oorlogskansen",page)
        self.assertNotIn("% kans",page)
if __name__=="__main__":unittest.main()
