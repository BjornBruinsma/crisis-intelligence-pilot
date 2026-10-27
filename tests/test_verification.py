"""Offline safety tests for human verification desk."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import build_verification as desk

class TestVerificationDesk(unittest.TestCase):
    def make_group(self,num,topic,priority=3):
        return {
          "key":str(num),
          "title":f"Iran announces evacuation <script>test({num})</script>",
          "categories":[topic],
          "day":"2026-10-27",
          "priority":"hoog" if priority==3 else "middel",
          "priority_level":priority,
          "priority_explanation":"Test headline only",
          "publishers":["Test publisher"],
          "article_count":1,
          "articles":[{"title":"Test title","url":"https://example.org/story",
                       "publisher":"Example News","published_at":"2026-10-27T09:00:00Z"}]
        }
    def test_category_balance(self):
        groups=[]
        for i in range(12): groups.append(self.make_group(i,desk.THEMES[0]))
        for i in range(12,24): groups.append(self.make_group(i,desk.THEMES[1]))
        result=desk.shortlist(groups,8)
        self.assertEqual(len(result),8)
        themes={x["discovered_via"] for x in result}
        self.assertEqual(len(themes),2)
        self.assertEqual(len([x for x in result if x["discovered_via"]==desk.THEMES[0]]),4)
        self.assertEqual(len([x for x in result if x["discovered_via"]==desk.THEMES[1]]),4)
    def test_unverified_claim_schema(self):
        items=desk.shortlist([self.make_group(1,desk.THEMES[0])])
        x=items[0]
        self.assertEqual(x["verification_status"],"unreviewed")
        self.assertIsNone(x["independent_corrob_count"])
        self.assertFalse(x["primary_evidence_confirmed"])
        self.assertFalse(x["publication_day_is_event_date"])
        self.assertIsNone(x["event_date"])
        self.assertEqual(x["sources"][0]["url"],"https://example.org/story")
    def test_html_is_escaped_and_exportable(self):
        groups=desk.shortlist([self.make_group(1,desk.THEMES[0])])
        webpage=desk.html_page({"candidates":groups,"source_groups_count":1})
        self.assertNotIn("<script>test(1)</script>",webpage)
        self.assertIn("&lt;script&gt;",webpage)
        self.assertIn("crisis-verification-annotations.json",webpage)
        self.assertIn("localStorage",webpage)
    def test_blocks_unsafe_links(self):
        self.assertEqual(desk.safe_url("javascript:alert(1)"),"#")
        self.assertEqual(desk.safe_url("https://example.com/path"),"https://example.com/path")

if __name__=="__main__":
    unittest.main()
