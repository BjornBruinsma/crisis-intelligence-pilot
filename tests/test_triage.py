"""Tests ensure automated editorial triage doesn't silently assert event truth."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import triage

class TestTriage(unittest.TestCase):
    def sample(self,title,date="2026-10-27T07:15:00Z",pub="Reuters"):
        return dict(title=title,publisher=pub,first_seen=date,published_at=date,
                    url="https://example.org/article",topic=["Politiek & diplomatie"])

    def test_near_duplicate_headlines_are_candidates_not_events(self):
        a=self.sample("Oil eases on Middle East diplomacy hopes, Saudi attacks keep worries alive - Reuters")
        b=self.sample("Oil eases on Middle East diplomacy hopes, Saudi attacks keep worries alive - CNBC",pub="CNBC")
        c=self.sample("Iran deploys new military personnel near the Gulf")
        groups=triage.cluster_articles([a,b,c])
        self.assertEqual(len(groups),2)
        merged=[x for x in groups if x["article_count"]==2][0]
        self.assertEqual(merged["review_status"],"unverified_story_candidate")
        self.assertEqual(merged["source_count"],2)

    def test_entertainment_does_not_dominate_queue(self):
        self.assertEqual(triage.editorial_rank(
            self.sample("Canelo boxer arrives in Riyadh as Iran warning looms"))[0],0)
        self.assertEqual(triage.editorial_rank(
            self.sample("Iran orders diplomats to evacuate embassy in Saudi Arabia"))[0],3)

    def test_no_score_computation_and_html_escaping(self):
        groups=triage.cluster_articles([self.sample('Iran "<script>alert(1)</script>" military attack')])
        self.assertTrue(groups[0]["priority"] in ("hoog","middel","laag"))
        page=triage.make_html(groups,{"article_count":1,"group_count":1,
            "priority_counts":{"hoog":1}})
        self.assertNotIn("<script>alert(1)</script>",page)
        self.assertIn("geen",page.lower())

if __name__=="__main__":
    unittest.main()
