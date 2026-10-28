"""Offline smoke tests for QA report. No API calls."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import quality_report as qa

class TestQualityReport(unittest.TestCase):
    def test_generated_report_does_not_claim_accuracy(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            data=root/"data"
            data.mkdir()
            documents={
                "articles.json":{"articles":[{"title":"A"},{"title":"B"}]},
                "review_queue.json":{"groups":[{"id":"g1"},{"id":"g2"}]},
                "verification_candidates.json":{"candidates":[{"id":"A"},{"id":"B"}]},
                "ai_assessments.json":{"status":"complete","assessments":{"A":{"relevance":"relevant"},
                                                                       "B":{"relevance":"relevant"}}},
                "event_candidates.json":{"status":"complete","input_candidate_count":2,
                    "clustering_method":"ai_pairwise_conservative",
                    "clustering_metrics":{"model_pair_proposals":1,"accepted_pair_connections":1,
                                          "rejected_pair_proposals":0},
                    "events":[{"headline_claim_ids":["A","B"],"verified_event":False,
                               "research_status":"no_matching_primary_evidence",
                               "primary_evidence":None}]},
                "primary_sources.json":{"sources":[{"authority":"Official","id":"doc","status":"ok",
                                                     "passages":["text"],"links":[]}]},
                "fetch_status.json":{"sources":{"google_news_rss":{"ok":12},
                                                  "gdelt_doc2":{"ok":0}}}
            }
            for name,doc in documents.items():
                (data/name).write_text(json.dumps(doc),encoding="utf-8")
            with patch.object(qa,"SITE",root),patch.object(qa,"DATA",data),patch.object(qa,"OUT",data/"quality_report.json"):
                qa.main()
            report=json.loads((data/"quality_report.json").read_text())
            t=report["technical"]
            self.assertTrue(t["ids_retained_without_duplicates"])
            self.assertEqual(t["multiple_claim_clusters"],1)
            self.assertEqual(t["verified_events"],0)
            self.assertIsNone(report["uncertainty"]["true_cluster_precision"])
            self.assertIsNone(report["uncertainty"]["true_cluster_recall"])
            self.assertIn("Geen specifieke officiële ondersteuning", " ".join(report["warnings"]))
            content=(root/"quality.html").read_text()
            self.assertIn("Kwaliteitscontrole",content)
            self.assertIn("Echte precisie/recall",content)

    def test_duplicate_or_missing_claim_id_is_flagged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); data=root/"data"; data.mkdir()
            cases={
                "verification_candidates.json":{"candidates":[{"id":"A"},{"id":"B"}]},
                "ai_assessments.json":{"assessments":{}},
                "event_candidates.json":{"status":"partial",
                    "events":[{"headline_claim_ids":["A","A"],"verified_event":False}]},
            }
            for name,obj in cases.items():(data/name).write_text(json.dumps(obj))
            with patch.object(qa,"SITE",root),patch.object(qa,"DATA",data),patch.object(qa,"OUT",data/"quality_report.json"):
                qa.main()
            report=json.loads((data/"quality_report.json").read_text())
            self.assertFalse(report["technical"]["ids_retained_without_duplicates"])
            self.assertTrue(any("ontbreekt of komt dubbel" in x for x in report["warnings"]))

if __name__=="__main__":unittest.main()
