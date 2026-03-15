from __future__ import annotations

import html as html_lib
import re
from dataclasses import dataclass
from typing import Any

import requests
from bs4 import BeautifulSoup
from requests import RequestException


GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/{board}?mode=json"

UK_LOCATION_HINTS = (
    "uk",
    "united kingdom",
    "london",
    "cambridge",
    "bristol",
    "belfast",
    "manchester",
    "edinburgh",
    "glasgow",
    "cardiff",
    "remote, united kingdom",
    "remote - united kingdom",
    "remote - uk",
    "oxford",
    "milton keynes",
    "coventry",
    "warwick",
    "silverstone",
    "derby",
    "southampton",
    "bicester",
    "reading",
    "leamington spa",
    "royal leamington spa",
    "nottingham",
    "birmingham",
)

ENGINEERING_TITLE_PATTERNS = (
    r"\bengineer(?:ing)?\b",
    r"\bdeveloper\b",
    r"\bsre\b",
    r"\bdevops\b",
    r"\bfirmware\b",
    r"\bsilicon\b",
    r"\bmechanical\b",
    r"\bmechatronics\b",
    r"\bautomotive\b",
    r"\baerospace\b",
    r"\bavionics\b",
    r"\bembedded\b",
    r"\brobotics?\b",
    r"\bautonomy\b",
    r"\b(?:vehicle|systems|controls|manufacturing|automation|hardware|quality|test)\s+engineer\b",
    r"\bfield engineer\b",
    r"\bfield service engineer\b",
    r"\bservice engineer\b",
    r"\btechnician\b",
    r"\bcad\b",
)
EXCLUDED_TITLE_HINTS = (
    "talent community",
    "brand designer",
    "product designer",
    "visual design",
    "graphic designer",
    "ux designer",
    "ui designer",
    "head of design",
)
SALARY_PATTERN = re.compile(
    r"([\u00A3\u0141]\s?\d{2,3}(?:,\d{3})+(?:\s?-\s?[\u00A3\u0141]\s?\d{2,3}(?:,\d{3})+)?)"
)
STOPWORDS = {
    "about",
    "after",
    "along",
    "also",
    "and",
    "are",
    "build",
    "candidate",
    "company",
    "deliver",
    "engineering",
    "experience",
    "have",
    "into",
    "need",
    "role",
    "team",
    "their",
    "they",
    "this",
    "through",
    "will",
    "with",
    "working",
}


@dataclass(frozen=True)
class CompanyFeed:
    company: str
    board: str
    provider: str
    careers_url: str


@dataclass(frozen=True)
class CompanyJob:
    company: str
    title: str
    location: str | None
    department: str | None
    salary: str | None
    duration: str | None
    summary: str
    key_requirements: list[str]
    apply_url: str
    source_provider: str
    source_board: str


STARTER_FEEDS = [
    CompanyFeed("Gearset", "gearset", "lever", "https://jobs.lever.co/gearset"),
    CompanyFeed("StarCompliance", "starcompliance", "lever", "https://jobs.lever.co/starcompliance"),
    CompanyFeed("Monzo", "monzo", "greenhouse", "https://job-boards.greenhouse.io/monzo"),
    CompanyFeed("Graphcore", "graphcore", "greenhouse", "https://job-boards.greenhouse.io/graphcore"),
    CompanyFeed("Anduril Industries", "andurilindustries", "greenhouse", "https://boards.greenhouse.io/andurilindustries"),
    CompanyFeed("Autotrader", "autotrader", "greenhouse", "https://job-boards.greenhouse.io/autotrader"),
    CompanyFeed("Jungheinrich", "jungheinrich", "greenhouse", "https://job-boards.greenhouse.io/jungheinrich"),
    CompanyFeed("Wayve", "wayve", "greenhouse", "https://wayve.firststage.co/jobs"),
]


def fetch_company_jobs(feeds: list[CompanyFeed] | None = None, timeout: int = 20) -> list[CompanyJob]:
    feeds = feeds or STARTER_FEEDS
    jobs: list[CompanyJob] = []

    for feed in feeds:
        try:
            if feed.provider == "lever":
                jobs.extend(_fetch_lever(feed, timeout))
            elif feed.provider == "greenhouse":
                jobs.extend(_fetch_greenhouse(feed, timeout))
        except RequestException:
            continue

    return jobs


def _fetch_lever(feed: CompanyFeed, timeout: int) -> list[CompanyJob]:
    payload = requests.get(LEVER_URL.format(board=feed.board), timeout=timeout).json()
    jobs: list[CompanyJob] = []

    for item in payload:
        title = item.get("text", "")
        location = item.get("categories", {}).get("location")
        department = item.get("categories", {}).get("department")
        duration = item.get("categories", {}).get("commitment")
        if not _is_target_job(title, location):
            continue

        description = "\n".join(
            [item.get("descriptionPlain", ""), item.get("additionalPlain", ""), _lists_to_text(item.get("lists", []))]
        ).strip()
        requirements = _extract_lever_requirements(item.get("lists", []))
        if not requirements:
            requirements = _extract_requirements(description)

        jobs.append(
            CompanyJob(
                company=feed.company,
                title=title,
                location=location,
                department=department,
                salary=_extract_salary(description),
                duration=duration,
                summary=_summarize_text(description),
                key_requirements=requirements,
                apply_url=item.get("hostedUrl", feed.careers_url),
                source_provider=feed.provider,
                source_board=feed.board,
            )
        )

    return jobs


def _fetch_greenhouse(feed: CompanyFeed, timeout: int) -> list[CompanyJob]:
    payload = requests.get(GREENHOUSE_URL.format(board=feed.board), timeout=timeout).json()
    jobs: list[CompanyJob] = []

    for item in payload.get("jobs", []):
        title = item.get("title", "")
        location = item.get("location", {}).get("name")
        department = _extract_greenhouse_department(item)
        if not _is_target_job(title, location):
            continue

        description = _fetch_greenhouse_job_text(item.get("absolute_url"), timeout)
        jobs.append(
            CompanyJob(
                company=feed.company,
                title=title.strip(),
                location=location,
                department=department,
                salary=_extract_salary(description),
                duration=_extract_duration(description),
                summary=_summarize_text(description),
                key_requirements=_extract_requirements(description),
                apply_url=item.get("absolute_url", feed.careers_url),
                source_provider=feed.provider,
                source_board=feed.board,
            )
        )

    return jobs


def _fetch_greenhouse_job_text(url: str | None, timeout: int) -> str:
    if not url:
        return ""

    html = requests.get(url, timeout=timeout).text
    return _greenhouse_page_to_text(html)


def _greenhouse_page_to_text(page_html: str) -> str:
    soup = BeautifulSoup(page_html or "", "html.parser")
    content = (
        soup.select_one("main")
        or soup.select_one("div[data-qa='job-description']")
        or soup.select_one("div#content")
        or soup.select_one("body")
    )
    if not content:
        return ""
    return _clean_text(content.get_text("\n", strip=True))


def _is_target_job(title: str, location: str | None) -> bool:
    title_l = (title or "").lower()
    location_l = (location or "").lower()

    if not any(re.search(pattern, title_l) for pattern in ENGINEERING_TITLE_PATTERNS):
        return False
    if any(hint in title_l for hint in EXCLUDED_TITLE_HINTS):
        return False
    if not any(hint in location_l for hint in UK_LOCATION_HINTS):
        return False
    return True


def _lists_to_text(items: list[dict[str, Any]]) -> str:
    chunks: list[str] = []
    for item in items or []:
        heading = item.get("text") or ""
        content = _html_to_text(item.get("content") or "")
        if heading or content:
            chunks.append(f"{heading}\n{content}".strip())
    return "\n".join(chunks)


def _extract_lever_requirements(items: list[dict[str, Any]], limit: int = 6) -> list[str]:
    heading_hints = (
        "who should apply",
        "who might thrive",
        "what you'll achieve",
        "requirements",
        "skills",
        "what we're looking for",
        "about you",
    )
    results: list[str] = []
    for item in items or []:
        heading = _clean_text(item.get("text") or "").lower()
        if not any(hint in heading for hint in heading_hints):
            continue
        soup = BeautifulSoup(item.get("content") or "", "html.parser")
        bullet_lines = [node.get_text(" ", strip=True) for node in soup.find_all("li")]
        if not bullet_lines:
            bullet_lines = _html_to_text(item.get("content") or "").splitlines()
        for line in bullet_lines:
            compact = re.sub(r"\s+", " ", line.strip(" -\u2022\t"))
            if len(compact) < 18:
                continue
            if compact not in results:
                results.append(compact)
            if len(results) >= limit:
                return results
    return results


def _html_to_text(html: str) -> str:
    unescaped = html_lib.unescape(html or "")
    soup = BeautifulSoup(unescaped, "html.parser")
    return _clean_text(soup.get_text("\n", strip=True))


def _extract_greenhouse_department(item: dict[str, Any]) -> str | None:
    departments = item.get("departments") or []
    if departments:
        first = departments[0]
        if isinstance(first, dict):
            return first.get("name")
    return None


def _extract_salary(text: str) -> str | None:
    match = SALARY_PATTERN.search(_clean_text(text or ""))
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip().replace("\u0141", "\u00A3")
    return None


def _extract_duration(text: str) -> str | None:
    text = _clean_text(text)
    patterns = [
        r"\b(full[- ]time|part[- ]time|contract|internship|graduate|placement|year in industry)\b",
        r"\b(\d{1,2}[- ]month)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _summarize_text(text: str, max_sentences: int = 2) -> str:
    cleaned = _clean_text(text)
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", cleaned) if part.strip()]
    return " ".join(sentences[:max_sentences])[:420]


def _extract_requirements(text: str, limit: int = 6) -> list[str]:
    lines = [line.strip(" -\u2022\t") for line in _clean_text(text).splitlines() if line.strip()]
    candidates: list[str] = []
    reject_markers = (
        "benefits",
        "perk",
        "holiday",
        "pension",
        "lunch",
        "salary",
        "budget",
        "insurance",
        "plan",
        "access to",
    )

    for line in lines:
        line_l = line.lower()
        if any(marker in line_l for marker in reject_markers):
            continue
        if any(
            marker in line_l
            for marker in (
                "you'll",
                "you will",
                "you have",
                "you are",
                "experience with",
                "looking for",
                "should have",
                "we need",
                "requirements",
                "skills",
            )
        ):
            candidates.append(line)

    if not candidates:
        candidates = lines

    cleaned: list[str] = []
    for line in candidates:
        compact = re.sub(r"\s+", " ", line)
        if len(compact) < 30:
            continue
        if compact.endswith(":"):
            continue
        if compact.lower().startswith("what you'll achieve"):
            continue
        if compact not in cleaned:
            cleaned.append(compact)
        if len(cleaned) >= limit:
            break

    if not cleaned:
        keywords = _extract_keyword_requirements(_clean_text(text), limit)
        return keywords

    return cleaned[:limit]


def _extract_keyword_requirements(text: str, limit: int) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-/+.]{2,}", text)
    keywords: list[str] = []
    reject = STOPWORDS.union({"company", "engineering", "experience", "working"})
    for token in tokens:
        token_l = token.lower()
        if token_l in reject:
            continue
        if token_l in keywords:
            continue
        if len(token_l) < 4 and token_l not in {"cad", ".net"}:
            continue
        keywords.append(token_l)
        if len(keywords) >= limit:
            break
    return keywords


def _clean_text(text: str) -> str:
    replacements = {
        "\xa0": " ",
        "\u00c2\u00a3": "\u00a3",
        "\u00c2": "",
        "\u00e2\u20ac\u2122": "'",
        "\u00e2\u20ac\u201c": "-",
        "\u00e2\u20ac\u201d": "-",
        "\u00e2\u20ac\u2014": "-",
        "â€”": "-",
        "â€“": "-",
        "\u00e2\u20ac": "\"",
        "\u0141": "\u00a3",
    }
    cleaned = text or ""
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    cleaned = re.sub(r"[\U00010000-\U0010FFFF]", "", cleaned)
    cleaned = cleaned.replace("\u00A3", "__GBP__")
    cleaned = cleaned.encode("ascii", "ignore").decode("ascii")
    cleaned = cleaned.replace("__GBP__", "\u00A3")
    return re.sub(r"\s+\n", "\n", cleaned).strip()
