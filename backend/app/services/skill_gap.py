"""Match configured skills against skills found in a job listing."""

import re

from bs4 import BeautifulSoup

from ..config import settings

KNOWN_SKILLS = [
    "python", "java", "javascript", "sql", "linux", "windows server", "active directory", "powershell",
    "bash", "networking", "tcp/ip", "dns", "dhcp", "vpn", "firewall", "cisco", "ccna", "ccnp", "juniper",
    "mikrotik", "routing", "switching", "vmware", "hyper-v", "aws", "azure", "gcp", "docker", "kubernetes",
    "terraform", "ansible", "git", "ci/cd", "siem", "splunk", "wazuh", "wireshark", "nmap", "owasp",
    "incident response", "penetration testing", "iso 27001", "itil", "ticketing", "office 365", "excel",
    "troubleshooting", "customer service", "communication", "teamwork", "problem solving", "time management",
    "project management", "data analysis", "data entry", "documentation", "research", "report writing",
    "attention to detail", "quality assurance", "process improvement", "risk management",
    "finance", "financial analysis", "accounting", "auditing", "compliance", "paraplanning",
    "administrative support", "accuracy", "reliability", "workflow management", "advice support",
    "technical support", "ip addressing", "subnetting", "computer hardware",
]

SKILL_ALIASES = {
    "javascript": ("js",),
    "sql": ("structured query language",),
    "linux": ("gnu/linux", "linux administration"),
    "active directory": ("microsoft active directory",),
    "windows server": ("microsoft windows server", "windows", "windows operating systems"),
    "networking": ("computer networking", "network administration", "lan", "wan", "vlan"),
    "technical support": ("it support", "help desk", "service desk"),
    "office 365": ("microsoft 365", "m365", "microsoft office"),
    "excel": ("microsoft excel", "ms excel", "spreadsheets"),
    "customer service": ("client service", "client support"),
    "communication": ("communicate", "communicating", "written communication", "verbal communication"),
    "problem solving": ("problem-solving",),
    "attention to detail": ("attention-to-detail", "detail oriented"),
    "quality assurance": ("quality review", "qa"),
    "process improvement": ("process enhancements", "continuous improvement"),
    "finance": ("financial",),
    "auditing": ("audit",),
    "administrative support": ("admin support", "administration", "administrative tasks"),
    "risk management": ("risk assessment",),
}

_TOPJOBS_ROLE_SKILLS = [
    (("cyber defense", "digital forensics", "information security", "cybersecurity", "cyber security"), [
        "siem", "incident response", "wireshark", "nmap", "iso 27001", "risk management",
    ]),
    (("business analyst",), [
        "sql", "excel", "data analysis", "communication", "problem solving", "documentation",
    ]),
    (("network", "telecommunication", "telecom", "cctv", "pbx"), [
        "networking", "tcp/ip", "dns", "dhcp", "troubleshooting", "computer hardware",
    ]),
    (("system engineer", "systems engineer", "system administrator", "systems administrator", "ict"), [
        "linux", "windows server", "networking", "troubleshooting", "powershell",
    ]),
    (("software engineer", "developer", "programmer"), [
        "python", "java", "javascript", "sql", "git", "problem solving",
    ]),
    (("it support", "it assistant", "it executive", "technical officer", "technical executive"), [
        "technical support", "troubleshooting", "communication", "problem solving", "documentation",
    ]),
    (("manager", "technology", "information technology", "it"), [
        "project management", "communication", "teamwork", "risk management", "documentation",
    ]),
]


def _plain_text(value: str) -> str:
    """Remove markup and decode escaped HTML, including feeds that encode it twice."""
    text = str(value or "")
    for _ in range(5):
        soup = BeautifulSoup(text, "lxml")
        for unwanted in soup(("script", "style", "noscript")):
            unwanted.decompose()
        decoded = soup.get_text(" ", strip=True)
        if decoded != text:
            text = decoded
            continue
        return decoded
    return text


def _normalize(value: str) -> str:
    value = str(value or "").casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9+#]+", " ", value).strip()


def _contains_skill(text: str, skill: str) -> bool:
    normalized = _normalize(skill)
    if not normalized:
        return False
    phrase = r"\s+".join(re.escape(word) for word in normalized.split())
    return bool(re.search(rf"(?<![a-z0-9]){phrase}(?![a-z0-9])", text))


def _catalog() -> dict[str, list[str]]:
    return {skill: [skill, *SKILL_ALIASES.get(skill, ())] for skill in KNOWN_SKILLS}


def _estimated_topjobs_skills(title: str) -> list[str]:
    normalized_title = _normalize(title)
    for role_terms, skills in _TOPJOBS_ROLE_SKILLS:
        if any(_contains_skill(normalized_title, term) for term in role_terms):
            return skills
    return []


def extract_resume_skills(text: str) -> list[str]:
    """Extract supported skill names from CV text without retaining the CV itself."""
    normalized_text = _normalize(_plain_text(text))
    return [
        skill for skill, variants in _catalog().items()
        if any(_contains_skill(normalized_text, variant) for variant in variants)
    ]


def analyze(
    text: str,
    user_skills: list[str] | None = None,
    source: str | None = None,
    title: str = "",
    details: str | None = None,
) -> dict:
    configured = (
        [skill.strip() for skill in settings.my_skills.split(",") if skill.strip()]
        if user_skills is None else [skill.strip() for skill in user_skills if skill.strip()]
    )
    normalized_text = _normalize(_plain_text(text))

    catalog = _catalog()
    alias_to_skill = {
        _normalize(alias): skill
        for skill, aliases in catalog.items()
        for alias in aliases
    }

    mine = set()
    for skill in configured:
        normalized = _normalize(skill)
        canonical = alias_to_skill.get(normalized, normalized)
        mine.add(canonical)
        if canonical not in catalog:
            # Include configured skills too, so custom skills such as Excel or
            # financial modelling can be matched even when they are not built in.
            catalog[canonical] = [skill]

    required = [
        skill for skill, variants in catalog.items()
        if any(_contains_skill(normalized_text, variant) for variant in variants)
    ]
    estimated = False
    estimate_unavailable = False
    if source == "topjobs":
        normalized_details = _normalize(_plain_text(details or ""))
        detail_skills = [
            skill for skill, variants in catalog.items()
            if any(_contains_skill(normalized_details, variant) for variant in variants)
        ]
        if not detail_skills:
            estimated = True
            inferred = _estimated_topjobs_skills(title)
            if inferred:
                required = inferred
            elif not required:
                estimate_unavailable = True

    have = [skill for skill in required if skill in mine]
    missing = [skill for skill in required if skill not in mine]
    percent = round(100 * len(have) / len(required)) if required and configured else None
    return {
        "match_percent": percent,
        "required": required,
        "have": have,
        "missing": missing,
        "estimated": estimated,
        "estimate_unavailable": estimate_unavailable,
        "skills_configured": bool(configured),
        "profile_source": "MY_SKILLS" if user_skills is None else "CV",
    }


def analyze_job(job, user_skills: list[str] | None = None) -> dict:
    details = f"{job.description} {job.requirements}"
    return analyze(
        f"{job.title} {details}",
        user_skills=user_skills,
        source=job.source,
        title=job.title,
        details=details,
    )
