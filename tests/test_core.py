import unittest

from job_agent.applicant_parser import parse_applicant_text
from job_agent.eligibility import classify_pakistan_eligibility
from job_agent.matching import match_job


class CoreTests(unittest.TestCase):
    def test_applicant_exact(self):
        x = parse_applicant_text("47 applicants", 100)
        self.assertEqual(x.count, 47)
        self.assertTrue(x.under_limit)

    def test_applicant_over(self):
        x = parse_applicant_text("Over 100 applicants", 100)
        self.assertIsNone(x.count)
        self.assertFalse(x.under_limit)

    def test_worldwide_eligible(self):
        status, _ = classify_pakistan_eligibility("This is a remote worldwide role. Work from anywhere.")
        self.assertEqual(status, "likely_eligible")

    def test_us_only_ineligible(self):
        status, _ = classify_pakistan_eligibility("Candidates must reside in the United States.")
        self.assertEqual(status, "ineligible")

    def test_missing_skill_is_exposed(self):
        profile = {
            "career": {"target_titles": ["Senior Product Manager"], "total_years_experience": 7},
            "skills": {
                "product_management": {"years": 7, "aliases": ["product management"], "evidence": ["roadmaps"]},
                "sql": {"years": 0, "aliases": ["sql"], "evidence": []},
            },
        }
        m = match_job("Senior Product Manager", "Requires product management and SQL experience", profile)
        self.assertIn("sql", m.missing_skills)
        self.assertIn("product_management", m.matched_skills)


if __name__ == "__main__":
    unittest.main()
