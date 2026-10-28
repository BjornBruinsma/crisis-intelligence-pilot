"""Tests for conservative AI grouping; no network or model calls."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import event_cluster as ec

def article(i,title,day="2026-10-28"):
    return {"id":i,"headline":title,"publication_day":day,
            "source_urls":["https://example.org/"+i],
            "editorial_importance":"medium"}

class TestPairwiseClustering(unittest.TestCase):
    def setUp(self):
        self.claims=[
            article("a","Iran warns about regional shipping"),
            article("b","Iran issues regional shipping warning"),
            article("c","Oil prices drop after the talks"),
            article("d","Iran conducts an actual airstrike"),
        ]
    def test_all_ids_preserved_without_model_group_enumeration(self):
        result,metrics=ec.validate_merge_pairs(
            {"merge_pairs":[{"a":"a","b":"b","why_nl":"Same specific warning"}]},self.claims)
        self.assertEqual(len(result),3)
        self.assertTrue(metrics["all_input_ids_retained"])
        self.assertEqual(metrics["accepted_pair_connections"],1)
        self.assertEqual(metrics["multi_claim_groups"],1)
        self.assertEqual(metrics["claims_in_multi_groups"],2)
        self.assertEqual({x for g in result for x in g["ids"]},set("abcd"))
        self.assertTrue(all(g["label_nl"].startswith("Claim: ") for g in result))
        self.assertTrue(all(g["event_date"] is None for g in result))
    def test_last_successful_groups_preserved_under_daily_limit(self):
        cache={"groups":[{"ids":["a","b"],"label_nl":"Claim: same warning",
                           "clustering_reason":"previously approved"},
                          {"ids":["c"],"label_nl":"Claim: oil prices",
                           "clustering_reason":"separate"}]}
        result=ec.reconstruct_cached_groups(self.claims,cache)
        self.assertEqual(len(result),3)
        self.assertEqual(result[0]["ids"],["a","b"])
        self.assertEqual({x for g in result for x in g["ids"]},set("abcd"))
    def test_cached_group_not_reused_if_member_disappears(self):
        cache={"groups":[{"ids":["a","missing"],"label_nl":"Claim: old group"},
                          {"ids":["b"],"label_nl":"Claim: other"}]}
        result=ec.reconstruct_cached_groups(self.claims,cache)
        self.assertEqual(len(result),4)
        self.assertFalse(any("missing" in g["ids"] for g in result))
        self.assertTrue(all(len(g["ids"])==1 for g in result))

    def test_empty_pairs_is_valid_and_never_drops_claims(self):
        result,metrics=ec.validate_merge_pairs({"merge_pairs":[]},self.claims)
        self.assertEqual(len(result),4)
        self.assertEqual(metrics["model_pair_proposals"],0)
    def test_hallucinated_duplicate_and_self_ids_rejected(self):
        result,metrics=ec.validate_merge_pairs(
            {"merge_pairs":[{"a":"a","b":"missing"},{"a":"a","b":"a"},
                {"a":"a","b":"b"},{"a":"b","b":"a"}]},self.claims)
        self.assertEqual(len(result),3)
        self.assertEqual(metrics["rejected_pair_proposals"],3)
        self.assertEqual(metrics["accepted_pair_connections"],1)
    def test_old_publication_not_automatically_combined(self):
        others=[article("a","Same headline","2026-10-20"),
                article("b","Same headline","2026-10-28")]
        result,metrics=ec.validate_merge_pairs(
           {"merge_pairs":[{"a":"a","b":"b"}]},others)
        self.assertEqual(len(result),2)
        self.assertEqual(metrics["accepted_pair_connections"],0)
    def test_missing_pairs_field_is_api_error(self):
        with self.assertRaises(ValueError):
            ec.validate_merge_pairs({"groups":[{"ids":["a"]}]},self.claims)
    def test_groups_are_never_verified_events(self):
        grouping,_=ec.validate_merge_pairs(
            {"merge_pairs":[{"a":"a","b":"b"}]},self.claims)
        out=ec.build_events(grouping,self.claims,{})
        self.assertTrue(all(x["verified_event"] is False for x in out))
        self.assertTrue(all(x["probability_estimate"] is None for x in out))

if __name__=="__main__":unittest.main()
