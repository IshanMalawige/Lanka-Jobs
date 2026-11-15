import unittest

from app.filters import classify, classify_level, experience_band, required_experience_years


class JobFilterClassificationTests(unittest.TestCase):
    def test_internships_use_the_interns_category(self):
        self.assertEqual(classify("Internship of Contact Centre Department"), "Interns")
        self.assertEqual(classify("Junior IT Support Engineer"), "IT Support")

    def test_classifies_junior_and_senior_position_levels(self):
        self.assertEqual(classify_level("Junior Network Engineer"), "junior")
        self.assertEqual(classify_level("Assistant Manager - IT"), "senior")
        self.assertEqual(classify_level("Senior Systems Engineer"), "senior")
        self.assertIsNone(classify_level("IT Support Engineer"))

    def test_extracts_numeric_and_written_experience_requirements(self):
        self.assertEqual(required_experience_years("At least 3 years of experience"), 3)
        self.assertEqual(required_experience_years("Two to five years' experience"), 2)
        self.assertEqual(experience_band("5+ years of relevant experience"), "4-5")
        self.assertEqual(experience_band("No prior experience required"), "0-1")
        self.assertEqual(experience_band("Experience preferred"), "unspecified")


if __name__ == "__main__":
    unittest.main()
