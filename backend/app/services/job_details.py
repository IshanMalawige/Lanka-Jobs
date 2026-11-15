"""Fetch and split the public details for jobs already saved in the database."""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from ..scrapers.base import HEADERS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_REDIRECTS = {301, 302, 303, 307, 308}
_REQUEST_DELAYS = {"linkedin": 5.0, "topjobs": 2.0, "itpro": 2.0, "xpress": 2.0, "careers": 2.0}
_TOPJOBS_PLACEHOLDER = re.compile(
    r"^please refer(?: to)? the full details of the job posting as given by the employer",
    re.IGNORECASE,
)
_TOPJOBS_DETAILS_FALLBACK = re.compile(
    r"^the employer did not provide a detailed description\.\s+available listing details:",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_OCR_ENGINE = None
_OCR_LOCK = Lock()
_MAX_POSTER_BYTES = 8 * 1024 * 1024

_REQUIREMENT_HEADINGS = {
    "requirements", "job requirements", "required skills", "skills required",
    "qualifications", "required qualifications", "experience and qualifications",
    "requirements and qualifications", "skills and experience", "education and experience",
    "what you will need", "what you'll need", "what you need", "what you will bring",
    "what you'll bring", "your profile", "who you are", "minimum requirements",
    "minimum qualifications", "technical requirements", "preferred skills",
    "what we are looking for", "what we're looking for", "candidate requirements",
    "experience", "education", "eligibility", "preferred qualifications",
}
_APPLICATION_HEADINGS = {
    "how to apply", "application instructions", "application process", "to apply",
    "how to apply for this role", "apply", "apply now", "method of application",
    "application procedure", "application method", "send your cv", "submit your application",
}
_DESCRIPTION_HEADINGS = {
    "job description", "about the job", "about the role", "role overview",
    "responsibilities", "key responsibilities", "what you will do", "what you'll do",
    "what we offer", "benefits", "about us", "about the company", "ideal candidate",
    "the role", "the opportunity", "duties and responsibilities", "job overview",
    "what you will be doing", "what you'll be doing",
}


def _allowed_host(url: str, source: str) -> bool:
    """Keep detail requests on the public job sites configured for this scraper."""
    try:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.lower().rstrip(".").removeprefix("www.")
        if source == "linkedin":
            return host == "linkedin.com" or host.endswith(".linkedin.com")
        if source == "topjobs":
            return host == "topjobs.lk" or host.endswith(".topjobs.lk")
        if source == "itpro":
            return host == "itpro.lk" or host.endswith(".itpro.lk")
        if source == "xpress":
            return host == "xpress.jobs" or host.endswith(".xpress.jobs")
        if source == "careers":
            # Career sites are explicitly configured in careers.py. Do not fetch arbitrary
            # extension URLs or follow an unrelated link from a career listing.
            from ..scrapers.careers import CAREER_SITES

            roots = set()
            for site in CAREER_SITES:
                site_host = urlsplit(site.get("url", "")).hostname
                if site_host:
                    roots.add(site_host.lower().rstrip(".").removeprefix("www."))
            return any(host == root or host.endswith("." + root) for root in roots)
    except (TypeError, ValueError):
        return False
    return False


def _html_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "\n".join(part for part in (_html_text(item) for item in value) if part)
    if isinstance(value, dict):
        return " ".join(part for part in (_html_text(v) for v in value.values()) if part)
    source = str(value)
    extracted = source
    # Some job feeds escape the markup inside their JSON-LD description. Parse
    # again after decoding so tags and entities do not leak into the saved text.
    for _ in range(5):
        soup = BeautifulSoup(extracted, "lxml")
        for unwanted in soup(("script", "style", "noscript")):
            unwanted.decompose()
        decoded = soup.get_text("\n", strip=True)
        if decoded != extracted:
            extracted = decoded
            continue
        extracted = decoded
        break
    lines = []
    for line in extracted.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip(" \t\r\n\u2022\u00b7")
        if cleaned and (not lines or cleaned != lines[-1]):
            lines.append(cleaned)
    return "\n".join(lines)


def _job_postings(value):
    if isinstance(value, list):
        for item in value:
            yield from _job_postings(item)
    elif isinstance(value, dict):
        types = value.get("@type", [])
        if isinstance(types, str):
            types = [types]
        if any(str(kind).lower().endswith("jobposting") for kind in types):
            yield value
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in value:
                yield from _job_postings(value[key])


def _jsonld_posting(soup: BeautifulSoup):
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            value = json.loads(script.string or script.get_text())
        except (TypeError, json.JSONDecodeError):
            continue
        posting = next(_job_postings(value), None)
        if posting:
            return posting
    return {}


def _safe_image_url(value, base_url: str) -> str:
    if isinstance(value, dict):
        for key in ("url", "contentUrl", "thumbnailUrl"):
            result = _safe_image_url(value.get(key), base_url)
            if result:
                return result
        return ""
    if isinstance(value, (list, tuple)):
        for item in value:
            result = _safe_image_url(item, base_url)
            if result:
                return result
        return ""
    if not isinstance(value, str) or not value.strip():
        return ""
    try:
        parsed = urlsplit(urljoin(base_url, value.strip()))
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return ""
    return parsed.geturl()


def _ocr_topjobs_poster(image_url: str) -> str:
    if not _allowed_host(image_url, "topjobs"):
        return ""

    image_bytes = bytearray()
    try:
        with requests.get(
            image_url, headers=HEADERS, timeout=20, stream=True, allow_redirects=False
        ) as response:
            response.raise_for_status()
            if not response.headers.get("Content-Type", "").lower().startswith("image/"):
                return ""
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if len(image_bytes) + len(chunk) > _MAX_POSTER_BYTES:
                    log.info("Skipping oversized TopJobs poster image: %s", image_url)
                    return ""
                image_bytes.extend(chunk)
    except requests.RequestException as exc:
        log.info("Could not fetch TopJobs poster image %s: %s", image_url, exc)
        return ""

    if not image_bytes:
        return ""

    try:
        import cv2
        import numpy as np
        from rapidocr import RapidOCR

        image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or image.shape[0] * image.shape[1] > 20_000_000:
            return ""

        global _OCR_ENGINE
        with _OCR_LOCK:
            if _OCR_ENGINE is None:
                _OCR_ENGINE = RapidOCR()
            result = _OCR_ENGINE(image)
        return "\n".join(
            text.strip()
            for text, score in zip(result.txts or (), result.scores or ())
            if text.strip() and score >= 0.35
        )
    except ImportError as exc:
        log.error("TopJobs poster OCR dependencies are unavailable: %s", exc)
    except Exception:
        log.exception("Could not read text from TopJobs poster image %s", image_url)
    return ""


def _image_in_markup(markup: str, base_url: str) -> str:
    soup = BeautifulSoup(markup, "lxml")
    for image in soup.find_all("img"):
        for attribute in ("data-src", "data-original", "src"):
            image_url = _safe_image_url(image.get(attribute), base_url)
            if image_url:
                return image_url
        srcset = image.get("srcset")
        if srcset:
            candidate = srcset.split(",", 1)[0].strip().split(" ", 1)[0]
            image_url = _safe_image_url(candidate, base_url)
            if image_url:
                return image_url
    return ""


def _extract_poster_image(soup: BeautifulSoup, posting: dict, url: str) -> str:
    description = posting.get("description")
    if isinstance(description, str):
        image_url = _image_in_markup(description, url)
        if image_url:
            return image_url

    selectors = (
        ".show-more-less-html__markup", ".description__text", ".jobs-description-content__text",
        '[itemprop="description"]', "#job-details", ".job-description", ".job-description__text",
        ".vacancy-description", "[class*='description__text']",
    )
    for selector in selectors:
        for node in soup.select(selector):
            image_url = _image_in_markup(node.decode_contents(), url)
            if image_url:
                return image_url

    image_url = _safe_image_url(posting.get("image"), url)
    if image_url:
        return image_url
    for selector in ('meta[property="og:image"]', 'meta[name="twitter:image"]'):
        meta = soup.select_one(selector)
        if meta:
            image_url = _safe_image_url(meta.get("content"), url)
            if image_url:
                return image_url
    return ""


def _heading(line: str):
    candidate = re.sub(r"^[#*\s\-]+|[#*\s]+$", "", line).strip()
    inline_text = ""
    if ":" in candidate:
        label, remainder = candidate.split(":", 1)
        if len(label) <= 60:
            candidate, inline_text = label.strip(), remainder.strip()
    normalized = re.sub(r"\s+", " ", candidate.lower()).strip(" .:-")
    if normalized in _REQUIREMENT_HEADINGS:
        return "requirements", inline_text
    if normalized in _APPLICATION_HEADINGS:
        return "how_to_apply", inline_text
    if normalized in _DESCRIPTION_HEADINGS:
        return "description", inline_text
    return None, ""


def _split_sections(text: str):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    sections = {"description": [], "requirements": [], "how_to_apply": []}
    active = "description"
    saw_section = False
    for line in lines:
        section, inline_text = _heading(line)
        if section:
            active = section
            saw_section = True
            if inline_text:
                sections[active].append(inline_text)
        else:
            sections[active].append(line)
    if not saw_section:
        sections["description"] = lines
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def _extract_text(soup: BeautifulSoup, posting: dict) -> str:
    # Prefer structured job data where the site provides it.
    if posting.get("description"):
        text = _html_text(posting["description"])
        if text and not _TOPJOBS_PLACEHOLDER.match(text):
            return text

    selectors = (
        ".show-more-less-html__markup", ".description__text", ".jobs-description-content__text",
        '[itemprop="description"]', "#job-details", ".job-description", ".job-description__text",
        ".vacancy-description", "[class*='description__text']", "article",
    )
    candidates = []
    for selector in selectors:
        for node in soup.select(selector):
            text = _html_text(node.decode_contents())
            if 80 <= len(text) <= 20000:
                candidates.append(text)
        if candidates:
            return max(candidates, key=len)

    body = soup.body or soup
    text = _html_text(body.decode_contents())
    if 80 <= len(text) <= 20000:
        # Avoid storing a whole sign-in or error page as a job description.
        lower = text.lower()
        if "join to apply" not in lower and "page not found" not in lower:
            return text
    return ""


def _topjobs_details(soup: BeautifulSoup, url: str, posting: dict) -> dict[str, str]:
    remark = soup.select_one("#remark")
    remark_markup = remark.decode_contents() if remark else ""
    description = _html_text(posting.get("description"))
    if _TOPJOBS_PLACEHOLDER.match(description):
        description = ""
    if not description:
        description = _html_text(remark_markup)

    facts = []
    header = soup.select_one(".ad-preview-screen .ad-header")
    if header:
        header_lines = _html_text(header.decode_contents()).splitlines()
        index = 0
        while index < len(header_lines):
            line = header_lines[index]
            if line.endswith(":") and index + 1 < len(header_lines):
                line = f"{line} {header_lines[index + 1]}"
                index += 1
            if line and line not in facts:
                facts.append(line)
            index += 1

    container = soup.select_one(".ad-preview-screen .container-fluid")
    if container:
        for row in container.find_all("div", class_="row", recursive=False):
            for line in _html_text(row.decode_contents()).splitlines():
                normalized = line.casefold()
                if line and not any(
                    term in normalized for term in ("apply by", "print", "sign up", "log in")
                ) and line not in facts:
                    facts.append(line)

    for location in posting.get("jobLocation", []) if isinstance(posting.get("jobLocation"), list) else [posting.get("jobLocation")]:
        if not isinstance(location, dict):
            continue
        address = location.get("address", {})
        if not isinstance(address, dict):
            continue
        locality = address.get("addressLocality")
        region = address.get("addressRegion")
        place = ", ".join(str(part) for part in (locality, region) if part)
        if place and not any(place.casefold() in fact.casefold() for fact in facts):
            facts.append(f"Location: {place}")
    for key, label in (("datePosted", "Posted"), ("validThrough", "Closing date")):
        value = posting.get(key)
        if isinstance(value, str) and value and not any(value in fact for fact in facts):
            facts.append(f"{label}: {value[:10]}")
    employment = posting.get("employmentType")
    employment_values = employment if isinstance(employment, list) else [employment]
    for value in employment_values:
        if isinstance(value, str) and value and not any(value.casefold() in fact.casefold() for fact in facts):
            facts.append(f"Employment type: {value.replace('_', ' ').title()}")

    image = ""
    remark_soup = BeautifulSoup(remark_markup, "lxml")
    for image_node in remark_soup.find_all("img"):
        image_urls = [
            _safe_image_url(image_node.get(attribute), url)
            for attribute in ("data-src", "data-original", "src")
        ]
        srcset = image_node.get("srcset")
        if srcset:
            image_urls.append(_safe_image_url(srcset.split(",", 1)[0].strip().split(" ", 1)[0], url))
        for image_url in image_urls:
            image_path = urlsplit(image_url).path.lower() if image_url else ""
            image_name = image_path.rsplit("/", 1)[-1]
            image_classes = image_node.get("class", [])
            is_company_logo = (
                "logo" in str(image_node.get("id", "")).lower()
                or any("logo" in class_name.lower() for class_name in image_classes)
                or image_name.endswith("_small.jpg")
                or bool(re.search(r"(?:company|employer)[-_]?logo", image_name))
            )
            if image_url and not is_company_logo and not image_path.endswith("/images/public/tj.jpg"):
                image = image_url
                break
        if image:
            break

    mailto_emails = " ".join(
        anchor.get("href", "").removeprefix("mailto:")
        for anchor in remark_soup.select('a[href^="mailto:"]')
    )
    email_source = f"{remark_markup}\n{description}\n{posting.get('email', '')}\n{mailto_emails}"
    email = _EMAIL_PATTERN.search(email_source)
    ocr_text = ""
    if image and (not description or _is_topjobs_placeholder(description) or not email):
        ocr_text = _ocr_topjobs_poster(image)
        if ocr_text and (not description or _is_topjobs_placeholder(description)):
            description = ocr_text

    if description and facts:
        description = "\n".join([*facts, "", f"Job description: {description}"])
    elif not description:
        summary = "\n".join(facts)
        description = (
            "The employer did not provide a detailed description. Available listing details:\n" + summary
            if summary else "The employer did not provide a detailed description on TopJobs."
        )

    details = _split_sections(description)
    email_source = f"{email_source}\n{description}\n{ocr_text}"
    email = _EMAIL_PATTERN.search(email_source)
    if email:
        details["how_to_apply"] = f"Send your CV to: {email.group(0)}"
    elif soup.select_one(".bottom-panel") and re.search(
        r"apply\s+by\s+online\s+cv", soup.select_one(".bottom-panel").get_text(" ", strip=True), re.I
    ):
        details["how_to_apply"] = "Apply through TopJobs using your online CV."
    else:
        details["how_to_apply"] = ""
    details["poster_image_url"] = image
    return details


def parse_job_details(html: str, url: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    posting = _jsonld_posting(soup)
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    if host == "topjobs.lk" or host.endswith(".topjobs.lk"):
        return _topjobs_details(soup, url, posting)

    poster_image_url = _extract_poster_image(soup, posting, url)
    source_text = _extract_text(soup, posting)
    details = _split_sections(source_text) if source_text else {
        "description": "", "requirements": "", "how_to_apply": "",
    }
    details["poster_image_url"] = poster_image_url

    qualifications = _html_text(posting.get("qualifications"))
    for key in ("educationRequirements", "experienceRequirements", "skills"):
        value = _html_text(posting.get(key))
        if value and value not in qualifications:
            qualifications = "\n".join(part for part in (qualifications, value) if part)
    if qualifications and not details["requirements"]:
        details["requirements"] = qualifications

    application_url = posting.get("applicationUrl") or posting.get("directApply")
    if isinstance(application_url, str) and application_url.startswith(("https://", "http://")):
        details["how_to_apply"] = "Apply online: " + application_url
    if not details["how_to_apply"]:
        apply_link = soup.find("a", string=re.compile(r"apply", re.I))
        if apply_link and apply_link.get("href"):
            apply_url = urljoin(url, apply_link["href"])
            apply_path = urlsplit(apply_url).path.lower()
            if urlsplit(apply_url).scheme in {"http", "https"} and not any(
                term in apply_path for term in ("login", "signin", "signup", "checkpoint")
            ):
                details["how_to_apply"] = "Apply online: " + apply_url

    return details


def _fetch_xpress_details(url: str) -> dict[str, str]:
    """XpressJobs serves job descriptions through its public JSON detail API."""
    match = re.search(r"/jobs/view/(\d+)(?:/|$)", urlsplit(url).path)
    if not match:
        return {"description": "", "requirements": "", "how_to_apply": "", "poster_image_url": ""}
    try:
        response = requests.get(
            "https://xpress.jobs/api/jobs/publishedJob",
            params={"jobId": match.group(1)},
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        posting = response.json()
        if not isinstance(posting, dict):
            return {"description": "", "requirements": "", "how_to_apply": "", "poster_image_url": ""}
    except (requests.RequestException, ValueError) as exc:
        log.info("Could not fetch XpressJobs details for %s: %s", url, exc)
        return {"description": "", "requirements": "", "how_to_apply": "", "poster_image_url": ""}

    requirements = "\n".join(
        part for part in (
            _html_text(posting.get("education")),
            _html_text(posting.get("experience")),
        ) if part
    )
    redirect_url = posting.get("redirectingUrl") if posting.get("isRedirected") else ""
    how_to_apply = (
        "Apply online: " + redirect_url
        if isinstance(redirect_url, str) and redirect_url.startswith("https://")
        else "Apply through XpressJobs: " + url
    )
    return {
        "description": _html_text(posting.get("jobInfo")),
        "requirements": requirements,
        "how_to_apply": how_to_apply,
        "poster_image_url": _safe_image_url(posting.get("jobImageUri"), url),
    }


def _is_topjobs_placeholder(value: str) -> bool:
    text = _html_text(value)
    return bool(
        _TOPJOBS_PLACEHOLDER.match(text)
        or _TOPJOBS_DETAILS_FALLBACK.match(text)
    )


def _is_topjobs_brand_image(value: str) -> bool:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    path = parsed.path.lower()
    image_name = path.rsplit("/", 1)[-1]
    return host == "topjobs.lk" and (
        path.endswith("/images/public/tj.jpg")
        or image_name.endswith("_small.jpg")
        or bool(re.search(r"(?:company|employer)[-_]?logo", image_name))
    )


def needs_job_details(job) -> bool:
    if not job.details_fetched_at:
        return True
    if job.source == "topjobs":
        return bool(
            _TOPJOBS_PLACEHOLDER.match(_html_text(job.description))
            or _is_topjobs_brand_image(job.poster_image_url)
        )
    return False


def apply_job_details(job, details: dict[str, str]) -> bool:
    changed = False
    for field in ("description", "requirements", "how_to_apply", "poster_image_url"):
        old_value = getattr(job, field)
        new_value = (details.get(field) or "").strip()
        replace_old = not old_value
        if job.source == "topjobs":
            replace_old = replace_old or (
                field == "description" and _is_topjobs_placeholder(old_value)
            ) or (
                field == "how_to_apply"
                and old_value.startswith("See the original job posting")
            ) or (
                field == "how_to_apply"
                and old_value.startswith("Apply through TopJobs using your online CV")
            ) or (
                field == "poster_image_url" and _is_topjobs_brand_image(old_value)
            )
        if new_value and replace_old and old_value != new_value:
            setattr(job, field, new_value)
            changed = True
        elif not new_value and field == "poster_image_url" and job.source == "topjobs" and _is_topjobs_brand_image(old_value):
            setattr(job, field, "")
            changed = True
    return changed


def refresh_single_job_details(db: Session, job, force: bool = False) -> bool:
    if not force and not needs_job_details(job):
        return False
    details = fetch_job_details(job.url, job.source)
    changed = apply_job_details(job, details)
    if job.description and not _TOPJOBS_PLACEHOLDER.match(_html_text(job.description)):
        fetched_at = datetime.utcnow()
        if job.details_fetched_at != fetched_at:
            job.details_fetched_at = fetched_at
            changed = True
    if changed:
        db.commit()
    return changed


def fetch_job_details(url: str, source: str) -> dict[str, str]:
    if not _allowed_host(url, source):
        return {"description": "", "requirements": "", "how_to_apply": "", "poster_image_url": ""}

    current_url = url
    try:
        time.sleep(_REQUEST_DELAYS.get(source, 2.0))
        if source == "xpress":
            return _fetch_xpress_details(url)
        for _ in range(4):
            if not _allowed_host(current_url, source):
                break
            response = requests.get(
                current_url, headers=HEADERS, timeout=20, allow_redirects=False
            )
            if response.status_code in _REDIRECTS:
                target = urljoin(current_url, response.headers.get("Location", ""))
                if target == current_url or not _allowed_host(target, source):
                    break
                current_url = target
                continue
            response.raise_for_status()
            if len(response.content) > 5_000_000:
                log.info("Skipping oversized job detail page: %s", current_url)
                break
            return parse_job_details(response.text, current_url)
    except requests.RequestException as exc:
        log.info("Could not fetch job details for %s: %s", url, exc)
    except Exception:
        log.exception("Could not parse job details for %s", url)
    return {"description": "", "requirements": "", "how_to_apply": "", "poster_image_url": ""}


def refresh_job_details(db: Session, force: bool = False) -> dict[str, int]:
    from ..models import Job

    query = db.query(Job).filter(Job.source.in_(("linkedin", "topjobs", "itpro", "xpress", "careers")))
    jobs = query.order_by(Job.id).all()
    if not force:
        jobs = [job for job in jobs if needs_job_details(job)]
    result = {"attempted": len(jobs), "updated": 0, "failed": 0}

    for job in jobs:
        if refresh_single_job_details(db, job, force=True):
            result["updated"] += 1
        if not job.description or _is_topjobs_placeholder(job.description):
            result["failed"] += 1
    return result
