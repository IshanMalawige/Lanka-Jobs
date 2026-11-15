"""Regex keyword filter: keeps only target IT roles and assigns a category."""
import re

CATEGORIES: dict[str, list[str]] = {
    "Interns": [r"\bintern(ship)?s?\b", r"\btrainee\b", r"\bgraduate\b", r"\bassociate\b"],
    "IT Support": [
        r"\bit\s+support\b", r"\bsystem\s+support\b", r"\bapplication\s+support\b",
        r"\bl[\s-]?[12]\s+support\b", r"\blevel\s+[12]\s+support\b", r"\bhelp\s?desk\b",
        r"\bservice\s+desk\b", r"\btechnical\s+support\b", r"\bsupport\s+(executive|engineer)\b",
    ],
    "Network": [r"\bnetwork\s+(engineer|administrator|admin|executive|officer)\b"],
    "Systems": [r"\bsystems?\s+(engineer|administrator|admin)\b", r"\bsysadmin\b", r"\bcloud\s+(engineer|administrator|support)\b", r"\bdevops\b"],
    "Security": [
        r"\bcyber\s?security\b", r"\bsoc\s+analyst\b", r"\bsecurity\s+(analyst|engineer|operations)\b",
        r"\binformation\s+security\b", r"\binfosec\b",
    ],
}
_COMPILED = {c: [re.compile(p, re.I) for p in pats] for c, pats in CATEGORIES.items()}

# Priority when a title matches several categories
PRIORITY = ["Security", "Network", "Systems", "IT Support", "Interns"]

EXCLUDE = re.compile(
    r"\b(sales|marketing|accountant|driver|chef|nurse|teacher|receptionist|"
    r"civil engineer|mechanical|electrical engineer|quantity surveyor)\b", re.I,
)
_JUNIOR_TITLE = re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|trainee|intern(ship)?)\b", re.I)
_SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager|director|head|chief)\b", re.I)
_ASSISTANT_TITLE = re.compile(r"\b(assistant|associate)\b", re.I)
_NO_EXPERIENCE = re.compile(r"\b(?:no|without)\s+(?:(?:prior|previous)\s+)?experience\b", re.I)
_NUMBER_WORD = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_NUMBER_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_RANGE_EXPERIENCE = re.compile(
    rf"\b({_NUMBER_WORD})\s*(?:-|–|—|to)\s*({_NUMBER_WORD})\s*(?:years?|yrs?)\b",
    re.I,
)
_MIN_EXPERIENCE = re.compile(
    rf"\b(?:at\s+least|minimum(?:\s+of)?|more\s+than|over)\s+({_NUMBER_WORD})\s*(?:years?|yrs?)\b",
    re.I,
)
_SINGLE_EXPERIENCE = re.compile(rf"\b({_NUMBER_WORD})\s*\+?\s*(?:years?|yrs?)\b", re.I)


def classify(title: str) -> str | None:
    """Return the category for a job title, or None if it is not a target role."""
    if not title or EXCLUDE.search(title):
        return None
    hits = [c for c, pats in _COMPILED.items() if any(p.search(title) for p in pats)]
    if not hits:
        return None
    for c in PRIORITY:
        if c in hits:
            return c
    return None


def classify_level(title: str) -> str | None:
    if _JUNIOR_TITLE.search(title or ""):
        return "junior"
    if _SENIOR_TITLE.search(title or ""):
        return "senior"
    if _ASSISTANT_TITLE.search(title or "") and not re.search(r"\bmanager\b", title or "", re.I):
        return "junior"
    return None


def required_experience_years(text: str) -> int | None:
    value = str(text or "")
    if _NO_EXPERIENCE.search(value):
        return 0
    for pattern in (_RANGE_EXPERIENCE, _MIN_EXPERIENCE, _SINGLE_EXPERIENCE):
        match = pattern.search(value)
        if match:
            number = match.group(1).lower()
            return _NUMBER_VALUES.get(number, int(number) if number.isdigit() else 0)
    return None


def experience_band(text: str) -> str:
    years = required_experience_years(text)
    if years is None:
        return "unspecified"
    if years <= 1:
        return "0-1"
    if years <= 3:
        return "2-3"
    if years <= 5:
        return "4-5"
    return "6+"
