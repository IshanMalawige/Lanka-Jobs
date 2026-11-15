"""Scrape IT and networking jobs from the public Xpress Jobs search API."""

import logging
from datetime import datetime

from .base import BaseScraper, RawJob

log = logging.getLogger("scraper")

SEARCH_URL = "https://xpress.jobs/api/jobs/searchJobs"
DETAIL_URL = "https://xpress.jobs/api/jobs/publishedJob"
IT_SECTORS = "139"
PAGE_SIZE = 100


class XpressScraper(BaseScraper):
    name = "xpress"
    # Xpress exposes a JSON search endpoint plus one public detail request per job.
    # A shorter delay keeps the initial sync useful while remaining gentle on the site.
    delay = 0.5

    def scrape(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen: set[int] = set()
        page = 1
        record_count: int | None = None

        while page <= 20:
            response = self.get(
                SEARCH_URL,
                params={
                    "page": page,
                    "pageSize": PAGE_SIZE,
                    "sectors": IT_SECTORS,
                },
            )
            if not response:
                break
            try:
                records = response.json()
            except ValueError:
                log.warning("%s: search API returned invalid JSON on page %s", self.name, page)
                break
            if not isinstance(records, list):
                log.warning("%s: search API returned an unexpected response on page %s", self.name, page)
                break
            if not records:
                break
            if record_count is None:
                record_count = max(
                    (int(item.get("recordCount", 0) or 0) for item in records if isinstance(item, dict)),
                    default=0,
                )

            for record in records:
                if not isinstance(record, dict):
                    continue
                try:
                    job_id = int(record.get("jobId"))
                except (TypeError, ValueError):
                    continue
                title = str(record.get("jobTitle") or "").strip()
                if not title or job_id in seen:
                    continue
                seen.add(job_id)
                url = f"https://xpress.jobs/jobs/view/{job_id}/"
                requirements = str(record.get("overview") or "").strip()
                jobs.append(RawJob(
                    title=title,
                    company=str(record.get("organizationName") or "").strip(),
                    url=url,
                    source=self.name,
                    requirements=requirements,
                ))

            if len(records) < PAGE_SIZE or (record_count and page * PAGE_SIZE >= record_count):
                break
            page += 1

        return jobs
