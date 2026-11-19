"""Offline checks for the HealthScope evidence pipeline.

Run: python -m unittest discover -s tests -v
"""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_briefs as gen
from research_sources import ArticleText, source_packet, short_public_provenance

class EvidencePipelineTests(unittest.TestCase):
    def test_source_domain_is_allowlisted(self):
        source=source_packet({"url":"https://example.org/private","title":"Example"})
        self.assertEqual(source["source_level"],"Metadata only")
        self.assertEqual(source["reason"],"Host is not allowlisted")

    def test_extract_article_without_navigation(self):
        reader=ArticleText()
        reader.feed("<html><nav>PRIVATE MENU</nav><main><article><h1>Research notes</h1><p>"
                    +("Healthcare data records need validation before use. "*15)
                    +"</p></article></main></html>")
        self.assertIn("Healthcare data records",reader.best())
        self.assertNotIn("PRIVATE MENU",reader.best())

    def test_quote_must_exist_in_source(self):
        text="A hospital recorded higher reporting completeness after a programme change, but its results were observational."
        self.assertTrue(gen.evidence_quote_matches("recorded higher reporting completeness after a programme change",text))
        self.assertFalse(gen.evidence_quote_matches("reporting improved and this saved thousands of lives",text))

    def test_default_brief_is_not_fake_research(self):
        record={"url":"https://pubmed.ncbi.nlm.nih.gov/12345678/","title":"Health information research",
                "source":"PubMed","source_type":"Research citation","category":"Digital health"}
        packet={"source_url":record["url"],"source_title":record["title"],
                "source_level":"Metadata only","method":"Retrieval unavailable",
                "retrieved_at":"2026-11-19T00:00:00Z",
                "study_type":"","reason":"unavailable"}
        brief=gen.fallback(record,packet)
        self.assertIn("not established",brief["evidence_status"].lower())
        self.assertIn("does not establish",brief["before"])
        self.assertEqual(len(brief["source_documents"]),1)
        self.assertIn("power_bi_deliverable",brief["analyst_exercise"])
        self.assertEqual(brief["support_quotes"],[])

    def test_recent_pub_dates(self):
        self.assertTrue(gen.fresh({"published":datetime.now(timezone.utc).strftime("%Y-%m-%d")}))
        self.assertFalse(gen.fresh({"published":"2020-08-24"}))
        self.assertFalse(gen.fresh({"published":""}))

    def test_no_article_text_is_published_in_source_trail(self):
        packet={"source_url":"https://clinicaltrials.gov/study/NCT12345678",
                "source_title":"A trial","text":"private not to publish",
                "source_level":"Primary source excerpt","retrieved_at":"today",
                "method":"API retrieval","study_type":"Interventional"}
        visible=short_public_provenance(packet)
        self.assertNotIn("text",visible)
        self.assertNotIn("private not to publish",str(visible))

if __name__ == "__main__":
    unittest.main()
