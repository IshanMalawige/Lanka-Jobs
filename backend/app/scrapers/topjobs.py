"""TopJobs.lk scraper.

The listing URLs and CSS selectors below may need adjusting if the site layout
changes: open the URL in your browser, inspect a job row, and update
`_parse_rows`.
"""
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from .base import BaseScraper, RawJob

LISTING_URLS = [
    "https://www.topjobs.lk/applicant/vacancybyfunctionalarea.jsp?FA=HNS",
]


class TopJobsScraper(BaseScraper):
    name = "topjobs"

    def scrape(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen: set[str] = set()
        for url in LISTING_URLS:
            r = self.get(url)
            if r:
                for job in self._parse_rows(r.text):
                    if job.url not in seen:
                        seen.add(job.url)
                        jobs.append(job)
        return jobs

    def _parse_rows(self, html: str) -> list[RawJob]:
        soup = BeautifulSoup(html, "lxml")
        out = []
        for row in soup.select("tr[id^=tr]"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            title_node = row.select_one("td:nth-of-type(3) h2")
            company_node = row.select_one("td:nth-of-type(3) h1")
            title = title_node.get_text(" ", strip=True) if title_node else ""
            company = company_node.get_text(" ", strip=True) if company_node else ""
            link = row.find("a", href=True)
            onclick = row.get("onclick", "")
            match = re.search(
                r"createAlert\(\s*'(\d+)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'\s*,\s*'([^']*)'",
                onclick,
            )
            if link:
                url = link["href"]
                if url.startswith("/"):
                    url = "https://www.topjobs.lk" + url
            elif match:
                row_id, agent_code, job_code, employer_code = match.groups()
                query = urlencode({
                    "rid": row_id,
                    "ac": agent_code,
                    "jc": job_code,
                    "ec": employer_code,
                    "pg": "applicant/vacancybyfunctionalarea.jsp",
                })
                url = f"https://www.topjobs.lk/employer/JobAdvertismentServlet?{query}"
            else:
                continue
            if title and company:
                out.append(RawJob(title=title, company=company, url=url, source=self.name))
        return out
