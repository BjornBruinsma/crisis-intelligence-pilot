"""Offline, no-network tests of optional AI editorial evaluation."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ai_assess as a


def item(k):
    return {"id":k,"headline_claim":"Iran threatens to close a shipping route",
            "discovered_via":"Wereldhandel & logistiek",
            "publication_day":"2026-10-27","article_count":1,
            "publisher_names":["Test Press"],
            "sources":[{"title":"Iran threatens to close a shipping route",
                        "publisher":"Test Press","url":"https://example.org/article"}]}


def result(k):
    return {"id":k,"relevance":"relevant","importance":"medium",
            "direction":"escalation","kind":"event_claim",
            "summary_nl":"De kop claimt een dreigement.",
            "claimed_event_nl":"Volgens de kop wordt een route bedreigd.",
            "reason_nl":"Relevant voor logistieke onzekerheid.",
            "limitations_nl":"Geen primaire bron of artikeltekst beschikbaar."}


class TestAssess(unittest.TestCase):
    def test_input_never_converts_headline_to_evidence(self):
        x=a.input_for(item("1"))
        self.assertIn("not_event",next(k for k in x if "not_event" in k))
        self.assertEqual(x["article_count_not_independent_corroborations"],1)
        self.assertEqual(x["headline"],"Iran threatens to close a shipping route")

    def test_validation_enforces_every_id_and_nonverified(self):
        out=a.validate({"results":[result("1")]},["1"])
        self.assertFalse(out["1"]["verified_event"])
        self.assertEqual(out["1"]["verification_status"],"not_verified_headlines_only")
        with self.assertRaises(ValueError):
            a.validate({"results":[result("2")]},["1"])
        with self.assertRaises(ValueError):
            a.validate({"results":[]},["1"])

    def test_cached_reviews_do_not_make_new_api_calls(self):
        v=a.validate({"results":[result("1")]},["1"])["1"]
        prior={"assessments":{"1":v},"usage_by_day":{}}
        with patch.object(a,"model_call") as api:
            res,usage,error=a.run_ai([item("1")],prior,"dummy-token")
        api.assert_not_called()
        self.assertEqual(error,None)
        self.assertIn("1",res)

    def test_batch_size_and_maximum_call_count(self):
        fake_usage={"prompt_tokens":15,"completion_tokens":20,"total_tokens":35}
        def fake_call(_token,batch):
            return {"results":[result(x["id"]) for x in batch]},fake_usage
        with patch.object(a,"model_call",side_effect=fake_call) as api, \
                patch.object(a.time,"sleep",return_value=None):
            res,_,error=a.run_ai([item(str(i)) for i in range(12)],
                                 {"assessments":{},"usage_by_day":{}},"dummy")
        self.assertIsNone(error)
        self.assertEqual(api.call_count,3)
        self.assertEqual(len(res),12)

    def test_escape_untrusted_headlines(self):
        x=item("1")
        x["headline_claim"]="<img src=x onerror=alert(1)>"
        data=a.validate({"results":[result("1")]},["1"])
        page=a.render_page([x],{"assessments":data,"status":"complete"})
        self.assertNotIn("<img src=x",page)
        self.assertIn("&lt;img",page)


if __name__=="__main__":
    unittest.main()
