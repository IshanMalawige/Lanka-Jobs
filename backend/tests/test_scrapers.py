import unittest
from unittest.mock import Mock, patch

from bs4 import BeautifulSoup

from app.scrapers.careers import BANKING_SOURCES, _job_links
from app.scrapers.topjobs import TopJobsScraper
from app.scrapers.xpress import SEARCH_URL, XpressScraper


class TopJobsScraperTests(unittest.TestCase):
    def test_parses_vacancy_rows_without_anchor_links(self):
        html = """
        <table>
          <tr id="tr0" onclick="createAlert('0','AGENT','000123','EMPLOYER','token')">
            <td>1</td><td>123</td>
            <td><h2>IT Support Engineer</h2><h1>Example Company</h1></td>
          </tr>
        </table>
        """

        jobs = TopJobsScraper()._parse_rows(html)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].title, "IT Support Engineer")
        self.assertEqual(jobs[0].company, "Example Company")
        self.assertEqual(
            jobs[0].url,
            "https://www.topjobs.lk/employer/JobAdvertismentServlet?"
            "rid=0&ac=AGENT&jc=000123&ec=EMPLOYER&pg=applicant%2Fvacancybyfunctionalarea.jsp",
        )


class XpressScraperTests(unittest.TestCase):
    @patch.object(XpressScraper, "get")
    def test_fetches_and_deduplicates_it_sector_search_results(self, get):
        response = Mock()
        response.json.return_value = [
            {"jobId": 123, "jobTitle": "IT Support Engineer", "organizationName": "Example Co", "overview": "Support users"},
            {"jobId": 123, "jobTitle": "IT Support Engineer", "organizationName": "Example Co", "overview": "Support users"},
        ]
        get.return_value = response

        jobs = XpressScraper().scrape()

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].source, "xpress")
        self.assertEqual(jobs[0].url, "https://xpress.jobs/jobs/view/123/")
        self.assertEqual(jobs[0].requirements, "Support users")
        get.assert_called_once_with(
            SEARCH_URL,
            params={"page": 1, "pageSize": 100, "sectors": "139"},
        )


class CareerSitesScraperTests(unittest.TestCase):
    def test_amana_source_points_to_vacancies_portal(self):
        amana = next(source for source in BANKING_SOURCES if source["company"] == "Amana Bank")

        self.assertEqual(amana["url"], "https://careers.amanabank.lk/")

    def test_skips_amana_career_overview_and_cloudflare_email_links(self):
        html = """
        <a href="/">Current Vacancies</a>
        <a href="/?pg=1">Careers available for you</a>
        <a href="/?pg=1">
          <h2>Careers available for you</h2><span>View vacancies</span>
        </a>
        <a href="/cdn-cgi/l/email-protection#1234">
          <h2>Be a part of an award winning dynamic team</h2>
        </a>
        <div>
          <a href="/vacancy/6/internship">
            <h2>Internship of Contact Centre Department</h2><span>Learn More</span>
          </a>
        </div>
        """

        jobs = _job_links(
            BeautifulSoup(html, "lxml"),
            "Amana Bank",
            "https://careers.amanabank.lk/",
            "amanabank.lk",
        )

        self.assertEqual([job.title for job in jobs], ["Internship of Contact Centre Department"])
        self.assertEqual(jobs[0].url, "https://careers.amanabank.lk/vacancy/6/internship")


if __name__ == "__main__":
    unittest.main()
