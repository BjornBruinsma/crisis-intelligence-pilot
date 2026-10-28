"""Regression checks for three observed false merges from the live pilot."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import event_cluster as ec

PAIRS=[
 ("Iran Targets U.S.Military Sites in Bahrain, Kuwait After American Strikes",
  "Iran targets Gulf countries' energy infrastructure after Israeli strike on gas field"),
 ("U.S. Evacuates Mideast Outposts After Suspected Iranian Plot to Target Americans",
  "State Department scrambles to help Americans stranded in Middle East war zone"),
 ("Oil Prices Rise as Iran Talks, Houthi Attacks and Middle East Tensions Keep Supply Fears Alive",
  "Oil Prices Fall as Traders Assess Iran Diplomacy, Saudi Attacks"),
]

class TestIndependentAudit(unittest.TestCase):
    def test_all_three_known_false_merges_vetoed_even_if_model_approves(self):
        for title_a,title_b in PAIRS:
            with self.subTest(first=title_a):
                claims=[{"id":"a","headline":title_a,"publication_day":"2026-10-28"},
                        {"id":"b","headline":title_b,"publication_day":"2026-10-28"}]
                proposed={"merge_pairs":[{"a":"a","b":"b","why_nl":"same region"}]}
                reviewer={"decisions":[{"a":"a","b":"b","same_event":True,"reason_nl":"similar"}]}
                groups,metrics=ec.independent_pair_audit(proposed,reviewer,claims)
                self.assertEqual(len(groups),2)
                self.assertEqual(metrics["accepted_pair_connections"],0)
                self.assertEqual(metrics["rule_rejected_pairs"],1)
                self.assertTrue(metrics["all_input_ids_retained"])
    def test_second_model_rejects_ambiguous_match(self):
        claims=[{"id":"a","headline":"Iran official warns about shipping","publication_day":"2026-10-28"},
                {"id":"b","headline":"Iran shipping warning during talks","publication_day":"2026-10-28"}]
        p={"merge_pairs":[{"a":"a","b":"b"}]}
        review={"decisions":[{"a":"a","b":"b","same_event":False,"reason_nl":"Not proven same action"}]}
        groups,metrics=ec.independent_pair_audit(p,review,claims)
        self.assertEqual(len(groups),2)
        self.assertEqual(metrics["rejected_pair_proposals"],1)
        self.assertEqual(metrics["rule_rejected_pairs"],0)
    def test_missing_review_response_is_fail_closed(self):
        with self.assertRaises(ValueError):
            ec.independent_pair_audit({"merge_pairs":[{"a":"a","b":"b"}]}, {},
               [{"id":"a","headline":"A"},{"id":"b","headline":"B"}])
    def test_approved_consistent_pair_can_be_merged(self):
        claims=[{"id":"a","headline":"Saudi tanker halted in Strait of Hormuz","publication_day":"2026-10-28"},
                {"id":"b","headline":"Tanker halted near Hormuz","publication_day":"2026-10-28"}]
        p={"merge_pairs":[{"a":"a","b":"b"}]}
        review={"decisions":[{"a":"a","b":"b","same_event":True}]}
        groups,metrics=ec.independent_pair_audit(p,review,claims)
        self.assertEqual(len(groups),1)
        self.assertEqual(metrics["accepted_pair_connections"],1)

if __name__=="__main__":unittest.main()
