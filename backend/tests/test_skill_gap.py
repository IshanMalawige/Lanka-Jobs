import unittest
from types import SimpleNamespace

from app.services.skill_gap import analyze_job


class TopJobsMatchTests(unittest.TestCase):
    def test_estimates_topjobs_match_from_role_title_when_requirements_are_missing(self):
        job = SimpleNamespace(
            source="topjobs",
            title="Business Analyst",
            description="The employer did not provide a detailed description.",
            requirements="",
        )

        match = analyze_job(job, user_skills=["sql", "excel"])

        self.assertEqual(match["match_percent"], 33)
        self.assertTrue(match["estimated"])
        self.assertEqual(match["have"], ["sql", "excel"])

    def test_uses_posted_topjobs_skills_when_the_description_contains_them(self):
        job = SimpleNamespace(
            source="topjobs",
            title="Business Analyst",
            description="Required skills: SQL and Excel.",
            requirements="",
        )

        match = analyze_job(job, user_skills=["sql"])

        self.assertEqual(match["match_percent"], 50)
        self.assertFalse(match["estimated"])
        self.assertEqual(match["required"], ["sql", "excel"])


if __name__ == "__main__":
    unittest.main()
