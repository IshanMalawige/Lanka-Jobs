import logging
import time
from dataclasses import dataclass
from datetime import datetime

import requests

log = logging.getLogger("scraper")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


@dataclass
class RawJob:
    title: str
    company: str
    url: str
    source: str
    posted_date: datetime | None = None
    description: str = ""
    requirements: str = ""
    how_to_apply: str = ""
    poster_image_url: str = ""


class BaseScraper:
    name = "base"
    delay = 2.0  # polite delay between requests

    def get(self, url: str, **kw) -> requests.Response | None:
        try:
            time.sleep(self.delay)
            r = requests.get(url, headers=HEADERS, timeout=20, **kw)
            r.raise_for_status()
            return r
        except Exception as e:  # network errors must never crash the scheduler
            log.warning("%s: request failed for %s: %s", self.name, url, e)
            return None

    def scrape(self) -> list[RawJob]:
        raise NotImplementedError
