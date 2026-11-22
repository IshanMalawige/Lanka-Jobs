import json
import unittest
from unittest.mock import patch

from app.services.job_details import parse_job_details


class PosterImageExtractionTests(unittest.TestCase):
    def test_extracts_image_from_structured_job_description(self):
        posting = {
            "@type": "JobPosting",
            "description": '<p>Role details</p><img data-src="/images/poster.jpg">',
        }
        html = f'<script type="application/ld+json">{json.dumps(posting)}</script>'

        details = parse_job_details(html, "https://jobs.example/jobs/123")

        self.assertEqual(details["poster_image_url"], "https://jobs.example/images/poster.jpg")

    def test_uses_open_graph_image_when_description_has_no_image(self):
        html = '<meta property="og:image" content="/images/poster.jpg">'

        details = parse_job_details(html, "https://jobs.example/jobs/123")

        self.assertEqual(details["poster_image_url"], "https://jobs.example/images/poster.jpg")

    def test_ignores_non_https_images(self):
        html = '<div class="job-description"><img src="http://images.example/poster.jpg"></div>'

        details = parse_job_details(html, "https://jobs.example/jobs/123")

        self.assertEqual(details["poster_image_url"], "")

    def test_extracts_topjobs_ad_details_email_and_poster_image(self):
        posting = {
            "@type": "JobPosting",
            "description": "Please refer the full details of the job posting as given by the employer.",
            "validThrough": "2027-01-15T00:00:00+0530",
            "employmentType": "FULL_TIME",
            "jobLocation": [{"address": {"addressLocality": "Colombo"}}],
        }
        html = f"""
        <script type="application/ld+json">{json.dumps(posting)}</script>
        <div class="ad-preview-screen">
          <div class="container-fluid">
            <div class="ad-header">Example Company<br>Colombo 2, Sri Lanka<br>Closing Date: 15/01/2027</div>
            <div class="row"><span>Full Time</span><span>Onsite</span><span>Apply by online CV</span></div>
            <div id="remark">
              <p>We need an IT support engineer.</p>
              <p>Requirements: Two years of experience.</p>
              <p>Send your CV to hr@example.com</p>
              <img src="/logo/0000000455/company-logo.png">
              <img src="/images/role-poster.jpg">
            </div>
          </div>
        </div>
        <img src="/images/public/tj.jpg">
        """

        details = parse_job_details(
            html,
            "https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
        )

        self.assertIn("We need an IT support engineer.", details["description"])
        self.assertIn("Closing Date: 15/01/2027", details["description"])
        self.assertNotIn("Please refer the full details", details["description"])
        self.assertIn("Two years of experience", details["requirements"])
        self.assertEqual(details["how_to_apply"], "Send your CV to: hr@example.com")
        self.assertEqual(details["poster_image_url"], "https://www.topjobs.lk/images/role-poster.jpg")

    def test_extracts_topjobs_poster_stored_under_logo_path(self):
        html = """
        <div class="ad-company-logo"><img id="logo" src="/logo/0000000605_small.jpg"></div>
        <div id="remark">
          <img src="/logo/0000000455/5115cTI.png">
        </div>
        """

        with patch("app.services.job_details._ocr_topjobs_poster", return_value=""):
            details = parse_job_details(
                html,
                "https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
            )

        self.assertEqual(
            details["poster_image_url"],
            "https://www.topjobs.lk/logo/0000000455/5115cTI.png",
        )

    def test_reads_topjobs_description_and_company_email_from_poster(self):
        image_url = "https://www.topjobs.lk/logo/DEFZZZ/1810c1006.png"
        poster_text = "\n".join([
            "Junior IT Support Executive",
            "Support UK clients and troubleshoot computer issues.",
            "Email your CV to aimposjobs@gmail.com",
        ])
        html = """
        <script type="application/ld+json">
          {"@type":"JobPosting","description":"Please refer the full details of the job posting as given by the employer."}
        </script>
        <div id="remark"><img src="/logo/DEFZZZ/1810c1006.png"></div>
        <div class="bottom-panel">Apply by online CV</div>
        """

        with (
            patch("app.services.job_details.settings.enable_ocr", True),
            patch("app.services.job_details._ocr_topjobs_poster", return_value=poster_text) as read_poster,
        ):
            details = parse_job_details(
                html,
                "https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
            )

        read_poster.assert_called_once_with(image_url)
        self.assertIn("Support UK clients", details["description"])
        self.assertNotIn("Please refer the full details", details["description"])
        self.assertEqual(details["how_to_apply"], "Send your CV to: aimposjobs@gmail.com")

    def test_skips_topjobs_poster_ocr_when_disabled(self):
        html = """
        <script type="application/ld+json">
          {"@type":"JobPosting","description":"Please refer the full details of the job posting as given by the employer."}
        </script>
        <div id="remark"><img src="/images/role-poster.png"></div>
        """

        with (
            patch("app.services.job_details.settings.enable_ocr", False),
            patch("app.services.job_details._ocr_topjobs_poster") as read_poster,
        ):
            details = parse_job_details(
                html,
                "https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
            )

        read_poster.assert_not_called()
        self.assertEqual(
            details["description"],
            "The employer did not provide a detailed description on TopJobs.",
        )
        self.assertEqual(
            details["poster_image_url"],
            "https://www.topjobs.lk/images/role-poster.png",
        )

    def test_topjobs_without_ad_description_uses_listing_facts_not_site_logo(self):
        posting = {
            "@type": "JobPosting",
            "description": "Please refer the full details of the job posting as given by the employer.",
        }
        html = f"""
        <script type="application/ld+json">{json.dumps(posting)}</script>
        <div class="ad-preview-screen">
          <div class="container-fluid">
            <div class="ad-header">Example Company<br>Colombo 2<br>Closing Date: 15/01/2027</div>
            <div class="row"><span>Full Time</span><span>Onsite</span></div>
            <div id="remark"></div>
          </div>
        </div>
        <div class="bottom-panel">Apply by online CV</div>
        <meta property="og:image" content="https://www.topjobs.lk/images/public/tj.jpg">
        """

        details = parse_job_details(
            html,
            "https://www.topjobs.lk/employer/JobAdvertismentServlet?jc=123",
        )

        self.assertIn("The employer did not provide a detailed description.", details["description"])
        self.assertIn("Closing Date: 15/01/2027", details["description"])
        self.assertNotIn("Please refer the full details", details["description"])
        self.assertIn("Apply through TopJobs", details["how_to_apply"])
        self.assertEqual(details["poster_image_url"], "")


if __name__ == "__main__":
    unittest.main()
