"""LinkedIn public guest job search.

Uses LinkedIn's unauthenticated 'jobs-guest' listing endpoint (no login). LinkedIn's
Terms of Service restrict automated scraping and the endpoint is rate limited, so
this scraper is deliberately slow and small. Use it for personal use only; the
browser extension is the safer way to add LinkedIn jobs.
"""
from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

SEARCH_TERMS = [
    "IT Support", "Application Support", "Network Engineer", "System Administrator",
    "Cloud Engineer", "SOC Analyst", "Cyber Security", "IT Intern",
]
API = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
       "?keywords={kw}&location=Sri%20Lanka&f_TPR=r604800&start=0")


class LinkedInScraper(BaseScraper):
    name = "linkedin"
    delay = 5.0

    def scrape(self) -> list[RawJob]:
        out: list[RawJob] = []
        for kw in SEARCH_TERMS:
            r = self.get(API.format(kw=kw.replace(" ", "%20")))
            if not r:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for card in soup.select("li"):
                a = card.select_one("a.base-card__full-link")
                t = card.select_one(".base-search-card__title")
                c = card.select_one(".base-search-card__subtitle")
                if not (a and t):
                    continue
                out.append(RawJob(
                    title=t.get_text(strip=True),
                    company=c.get_text(strip=True) if c else "",
                    url=a["href"].split("?")[0],
                    source=self.name,
                ))
        return out
