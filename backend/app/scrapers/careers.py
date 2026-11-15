"""Collect public openings from the configured Sri Lankan bank career pages."""
import json
import logging
import re
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .base import BaseScraper, RawJob

log = logging.getLogger("scraper")

# Keep the official destinations in one place for the scraper and dashboard directory.
BANKING_SOURCES: list[dict[str, str]] = [
    {"company": "Bank of Ceylon (BOC)", "group": "State-owned", "url": "https://www.boc.lk/careers"},
    {"company": "People's Bank", "group": "State-owned", "url": "https://www.peoplesbank.lk"},
    {"company": "National Savings Bank (NSB)", "group": "State-owned", "url": "https://www.nsb.lk/careers/"},
    {"company": "Hatton National Bank (HNB)", "group": "Private bank", "url": "https://www.hnb.lk/about-us/careers/current-openings"},
    {"company": "Commercial Bank of Ceylon", "group": "Private bank", "url": "https://www.combank.lk/careers"},
    {"company": "Sampath Bank", "group": "Private bank", "url": "https://www.sampath.lk/careers?page_name=Overview"},
    {"company": "DFCC Bank", "group": "Private bank", "url": "https://www.dfcc.lk/people/career-opportunities/career-opportunities-at-dfcc"},
    {"company": "National Development Bank (NDB)", "group": "Private bank", "url": "https://www.ndbbank.com"},
    {"company": "Pan Asia Bank", "group": "Private bank", "url": "https://www.pabcbank.com/about-us/careers/"},
    {"company": "Seylan Bank", "group": "Private bank", "url": "https://www.seylan.lk"},
    {"company": "Nations Trust Bank (NTB)", "group": "Private bank", "url": "https://www.nationstrust.com"},
    {"company": "Amana Bank", "group": "Private bank", "url": "https://careers.amanabank.lk/"},
    {"company": "Sanathana Development Bank (SDB)", "group": "Private bank", "url": "https://www.sdb.lk/en/about-us/careers"},
    {"company": "Cargills Bank", "group": "Private bank", "url": "https://www.cargillsbank.com"},
    {"company": "Central Bank of Sri Lanka (CBSL)", "group": "Regulator", "url": "https://www.cbsl.lk/RecruitmentPortal/"},
]

CAREER_SITES = BANKING_SOURCES

_GENERIC_LINK_TEXT = re.compile(
    r"^(apply(?:\s+(?:now|online))?|view(?:\s+more|\s+job)?|read\s+more|details|more|learn\s+more|"
    r"english|sinhala|tamil|සිංහල|தமிழ்)$", re.I
)
_CAREER_LINK = re.compile(r"career|vacanc|recruit|job|opening|position|people\s*(?:&|and)\s*culture", re.I)
_LISTING_PAGE_LINK = re.compile(
    r"(?:view\s+(?:open\s+)?(?:vacanc|job)|current\s+(?:job|vacanc|opening)|open\s+vacanc|"
    r"job\s+opportunit|recruitment\s+opportunit|vacancies)", re.I
)
_JOB_PATH = re.compile(r"job|vacan|opening|position|recruit|opportunit", re.I)
_LISTING_PATH = re.compile(r"/(?:careers?|jobs?|vacancies|openings|job-listings)/?$", re.I)
_ACTION_TEXT = re.compile(r"apply|closing\s+date|view\s+more|job\s+description|vacanc", re.I)
_SKIP_PATH = re.compile(r"/(?:contact|privacy|terms|login|signin|signup|facebook|instagram|linkedin)(?:/|$)", re.I)
_EMAIL_PROTECTION_PATH = re.compile(r"/cdn-cgi/l/email-protection(?:/|$)", re.I)
_CAREER_OVERVIEW_TITLE = re.compile(
    r"^(?:current\s+vacancies|careers?\s+available\s+for\s+you|"
    r"start\s+your\s+career(?:\s+with\s+.+)?|careers?\s+working\s+at\s+.+)$",
    re.I,
)


def _same_site(url: str, root_host: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower().rstrip(".").removeprefix("www.")
        root_host = root_host.lower().rstrip(".").removeprefix("www.")
        return parsed.scheme == "https" and (host == root_host or host.endswith("." + root_host))
    except ValueError:
        return False


def _posting_objects(value):
    if isinstance(value, list):
        for item in value:
            yield from _posting_objects(item)
    elif isinstance(value, dict):
        kinds = value.get("@type", [])
        if isinstance(kinds, str):
            kinds = [kinds]
        if any(str(kind).lower().endswith("jobposting") for kind in kinds):
            yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                yield from _posting_objects(value[key])


def _jsonld_jobs(soup: BeautifulSoup, company: str, page_url: str) -> list[RawJob]:
    jobs: list[RawJob] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        for item in _posting_objects(value):
            title = " ".join(str(item.get("title", "")).split())
            url = item.get("url") or item.get("mainEntityOfPage") or page_url
            if isinstance(url, dict):
                url = url.get("@id", "")
            url = urljoin(page_url, str(url))
            if not title or not _same_site(url, urlsplit(page_url).hostname or ""):
                continue
            posted = None
            raw_date = item.get("datePosted")
            if raw_date:
                try:
                    posted = datetime.fromisoformat(str(raw_date).replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    pass
            requirements = item.get("qualifications") or item.get("skills") or ""
            description = item.get("description") or ""
            how_to_apply = item.get("applicationUrl") or ""
            jobs.append(RawJob(
                title=title, company=company, url=url, source="careers", posted_date=posted,
                description=str(description), requirements=str(requirements),
                how_to_apply=str(how_to_apply),
            ))
    return jobs


def _text(node) -> str:
    return " ".join(node.stripped_strings) if node else ""


def _job_links(soup: BeautifulSoup, company: str, page_url: str, root_host: str) -> list[RawJob]:
    jobs: list[RawJob] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        href = str(anchor.get("href", "")).strip()
        url = urljoin(page_url, href)
        parsed = urlsplit(url)
        current = urlsplit(page_url)
        same_document = (parsed.scheme, parsed.netloc, parsed.path, parsed.query) == (
            current.scheme, current.netloc, current.path, current.query
        )
        if (not _same_site(url, root_host) or not parsed.path or _SKIP_PATH.search(parsed.path)
                or _EMAIL_PROTECTION_PATH.search(parsed.path)
                or (parsed.hostname or "").lower().startswith("forms.")
                or _LISTING_PATH.search(parsed.path.rstrip("/"))
                or (same_document and not parsed.fragment)):
            continue

        link_text = _text(anchor)
        if not link_text:
            continue
        if (
            (parsed.path.rstrip("/") in {"", "/"} and _CAREER_LINK.search(link_text))
            or (
                _CAREER_OVERVIEW_TITLE.fullmatch(link_text.strip())
                and not _JOB_PATH.search(parsed.path)
            )
        ):
            continue

        containers = [anchor]
        containers.extend(parent for parent in list(anchor.parents)[:5] if getattr(parent, "name", None))
        title = ""
        for container in containers:
            container_text = _text(container)
            if not container_text or len(container_text) > 900:
                continue
            heading = container.select_one("h1, h2, h3, h4, h5, [class*='job-title'], [class*='vacancy-title']")
            heading_text = _text(heading)
            has_action = bool(_ACTION_TEXT.search(container_text))
            if heading_text and (has_action or _JOB_PATH.search(parsed.path)):
                title = heading_text
                break
            if container.name == "li" and has_action:
                title = _GENERIC_LINK_TEXT.sub("", container_text).strip(" \t\r\n-:|·")
                if title:
                    break

        link_is_action = bool(_GENERIC_LINK_TEXT.fullmatch(link_text.strip()))
        if not title and not link_is_action and _JOB_PATH.search(parsed.path):
            title = link_text
        if not title:
            continue

        title = re.sub(r"\s*(?:apply\s+now|view\s+more|read\s+more|closing\s+date\s*:?).*$", "", title, flags=re.I).strip(" \t\r\n-:|·")
        if _CAREER_OVERVIEW_TITLE.fullmatch(title) and not _JOB_PATH.search(parsed.path):
            continue
        if (len(title) < 4 or len(title) > 180 or _GENERIC_LINK_TEXT.fullmatch(title.strip())
                or title.lower() in {
            "careers", "career opportunities", "current opportunities", "current openings",
            "open vacancies", "view open vacancies", "view all jobs", "view all vacancies",
        }):
            continue
        if not (_JOB_PATH.search(parsed.path) or _ACTION_TEXT.search(_text(containers[-1])) or link_is_action):
            continue
        if url in seen:
            continue
        seen.add(url)
        jobs.append(RawJob(title=title, company=company, url=url, source="careers"))
    return jobs


def _career_pages(soup: BeautifulSoup, current_url: str, root_host: str) -> list[str]:
    pages = []
    for anchor in soup.select("a[href]"):
        label = _text(anchor)
        url = urljoin(current_url, str(anchor.get("href", "")))
        path = urlsplit(url).path
        if (label and _CAREER_LINK.search(label) and _same_site(url, root_host)
                and not _JOB_PATH.search(path) and not _SKIP_PATH.search(path)
                and url.rstrip("/") != current_url.rstrip("/")):
            pages.append(url)
    return list(dict.fromkeys(pages))


def _listing_pages(soup: BeautifulSoup, current_url: str, root_host: str) -> list[str]:
    pages = []
    for anchor in soup.select("a[href]"):
        label = _text(anchor)
        url = urljoin(current_url, str(anchor.get("href", "")))
        path = urlsplit(url).path
        if (label and _LISTING_PAGE_LINK.search(label) and _same_site(url, root_host)
                and not _SKIP_PATH.search(path) and url.rstrip("/") != current_url.rstrip("/")):
            pages.append(url)
    return list(dict.fromkeys(pages))


class CareerSitesScraper(BaseScraper):
    name = "careers"

    def scrape(self) -> list[RawJob]:
        out: list[RawJob] = []
        seen_jobs: set[str] = set()
        for site in CAREER_SITES:
            configured_url = site["url"]
            root_host = (urlsplit(configured_url).hostname or "").lower().rstrip(".").removeprefix("www.")
            if not root_host:
                continue
            pending = [configured_url]
            visited: set[str] = set()
            while pending and len(visited) < 3:
                page_url = pending.pop(0)
                if page_url in visited:
                    continue
                visited.add(page_url)
                response = self.get(page_url)
                if not response:
                    continue
                page_url = response.url or page_url
                soup = BeautifulSoup(response.text, "lxml")
                page_jobs = _jsonld_jobs(soup, site["company"], page_url)
                page_jobs.extend(_job_links(soup, site["company"], page_url, root_host))
                for job in page_jobs:
                    if job.url not in seen_jobs:
                        seen_jobs.add(job.url)
                        out.append(job)

                # Some destinations are home pages or career overview pages. Follow a
                # few explicitly labeled, same-bank career and vacancy-listing links.
                linked_pages = _listing_pages(soup, page_url, root_host)
                linked_pages.extend(_career_pages(soup, page_url, root_host))
                pending.extend(url for url in dict.fromkeys(linked_pages) if url not in visited)
        log.info("bank career scraper found %s listings", len(out))
        return out
