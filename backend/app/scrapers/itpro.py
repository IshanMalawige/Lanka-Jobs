"""Scrape public IT roles from the selected ITPro.lk job categories."""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

LISTING_URLS = [
    "https://itpro.lk/jobs/information-technology/",
    "https://itpro.lk/jobs/hardware-networking/",
]

_JOB_LINK = re.compile(r"^/job/\d+/")


def _text(node) -> str:
    if not node:
        return ""
    value = node.get("content") or node.get("title") or node.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", str(value)).strip()


def _card_for(anchor):
    parents = list(anchor.parents)[:7]
    for parent in parents:
        if getattr(parent, "name", None) not in {"article", "li", "div", "section"}:
            continue
        classes = " ".join(parent.get("class", []))
        if re.search(r"(?:job|vacanc|listing|search)[-_ ]?(?:card|item|result|listing)|(?:card|item)[-_ ]?(?:job|vacanc|listing)", classes, re.I):
            return parent
    for parent in parents:
        if getattr(parent, "name", None) in {"article", "li"}:
            return parent
    return anchor


def _field(card, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = card.select_one(selector)
        value = _text(node)
        if value:
            return value
    return ""


def _next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    for anchor in soup.select("a[href]"):
        label = _text(anchor).lower()
        aria = str(anchor.get("aria-label", "")).lower()
        classes = " ".join(anchor.get("class", []))
        if not label.startswith("next") and "next" not in aria and not re.search(r"\bnext\b", classes, re.I):
            continue
        target = urljoin(current_url, str(anchor.get("href", "")))
        parsed = urlsplit(target)
        if parsed.scheme == "https" and parsed.hostname and parsed.hostname.lower().removeprefix("www.") == "itpro.lk":
            return target
    return None


class ITProScraper(BaseScraper):
    name = "itpro"

    def scrape(self) -> list[RawJob]:
        jobs: list[RawJob] = []
        seen: set[str] = set()
        for listing_url in LISTING_URLS:
            page_url: str | None = listing_url
            visited: set[str] = set()
            while page_url and page_url not in visited and len(visited) < 10:
                visited.add(page_url)
                response = self.get(page_url)
                if not response:
                    break
                page_url = response.url or page_url
                soup = BeautifulSoup(response.text, "lxml")
                for job in self._parse_listing(soup, page_url):
                    if job.url not in seen:
                        seen.add(job.url)
                        jobs.append(job)
                page_url = _next_page(soup, page_url)
        return jobs

    def _parse_listing(self, soup: BeautifulSoup, page_url: str) -> list[RawJob]:
        jobs: list[RawJob] = []
        for anchor in soup.select("a[href]"):
            href = str(anchor.get("href", "")).strip()
            target = urljoin(page_url, href)
            parsed = urlsplit(target)
            if (not _JOB_LINK.match(parsed.path) or parsed.scheme != "https" or not parsed.hostname
                    or parsed.hostname.lower().removeprefix("www.") != "itpro.lk"):
                continue

            card = _card_for(anchor)
            title = _field(card, (
                "[itemprop='title']", "[class*='job-title']", "[class*='title']",
                "h1", "h2", "h3", "h4", "h5",
            ))
            company = _field(card, (
                "[itemprop='hiringOrganization']", "[class*='company-name']",
                "[class*='company']", "[data-company]", "a[href*='/company/']",
            ))
            if not title:
                chunks = [re.sub(r"\s+", " ", chunk).strip() for chunk in anchor.stripped_strings]
                title = next((chunk for chunk in chunks if 4 <= len(chunk) <= 180), "")
                if not company and len(chunks) > 1:
                    company = chunks[1]
            if not title or len(title) > 180:
                continue

            jobs.append(RawJob(
                title=title, company=company, url=target, source=self.name,
            ))
        return jobs
