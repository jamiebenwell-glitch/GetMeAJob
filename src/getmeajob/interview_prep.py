from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse
import re

import httpx
from bs4 import BeautifulSoup


SEARCH_URL = "https://lite.duckduckgo.com/lite/"
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )
}
DOUBLE_SUFFIXES = {"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "co.nz"}
ATS_DOMAINS = (
    "greenhouse.io",
    "job-boards.greenhouse.io",
    "boards.greenhouse.io",
    "lever.co",
    "jobs.lever.co",
    "workdayjobs.com",
    "myworkdayjobs.com",
    "ashbyhq.com",
    "boards.greenhouse.io",
    "smartrecruiters.com",
    "breezy.hr",
    "jobvite.com",
)
EXCLUDED_SEARCH_DOMAINS = ATS_DOMAINS + (
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "linkedin.com",
    "linkedin.cn",
    "facebook.com",
    "instagram.com",
    "youtube.com",
)
COMMUNITY_DOMAINS = (
    "reddit.com",
    "indeed.com",
    "ambitionbox.com",
    "interviewquery.com",
    "interviewpal.com",
)
PROCESS_STAGE_HINTS = [
    ("Recruiter screen", ("recruiter", "phone screen", "screening call", "intro call", "initial chat")),
    ("Hiring manager interview", ("hiring manager", "manager interview", "team interview", "team fit")),
    ("Technical deep dive", ("technical interview", "coding interview", "system design", "design review", "technical screen", "project deep dive", "portfolio review")),
    ("Assessment or task", ("take-home", "take home", "assignment", "assessment", "exercise", "case study", "presentation", "pair programming")),
    ("Final panel", ("panel", "final interview", "onsite", "on-site", "loop", "behavioural", "behavioral")),
]
SIGNAL_HINTS = {
    "Customer focus": ("customer", "user", "member", "client"),
    "Ownership": ("ownership", "own", "initiative", "drive"),
    "Speed and ambiguity": ("fast-paced", "ambiguity", "move quickly", "iterate", "pragmatic"),
    "Collaboration": ("collaboration", "cross-functional", "team", "stakeholder"),
    "Quality and safety": ("quality", "safety", "reliability", "detail", "rigour", "rigor"),
    "Learning and growth": ("learn", "growth", "curiosity", "develop", "mentoring"),
}


@dataclass
class PrepSource:
    title: str
    url: str
    source_type: str
    domain: str


@dataclass
class PrepStage:
    name: str
    detail: str
    confidence: str
    source_title: str
    source_url: str


@dataclass
class PrepSignal:
    title: str
    detail: str
    source_title: str
    source_url: str


@dataclass
class PrepQuestion:
    question: str
    why: str
    anchor: str


@dataclass
class PrepQuestionGroup:
    title: str
    description: str
    questions: list[PrepQuestion]


def _clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _host_from_url(url: str) -> str:
    return urlparse(url).netloc.lower()


def _registrable_domain(host: str) -> str:
    host = host.split(":")[0].lower().strip(".")
    parts = [part for part in host.split(".") if part]
    if len(parts) <= 2:
        return host
    suffix = ".".join(parts[-2:])
    if suffix in DOUBLE_SUFFIXES and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def _base_url(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _unwrap_duckduckgo_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" not in parsed.netloc:
        return url
    query = parse_qs(parsed.query)
    target = query.get("uddg", [""])[0]
    return unquote(target) if target else url


def _is_ats_domain(domain: str) -> bool:
    root = _registrable_domain(domain)
    return any(root.endswith(item) for item in ATS_DOMAINS)


def _slug_to_name(slug: str) -> str:
    slug = re.sub(r"[-_]+", " ", slug or "").strip()
    return " ".join(part.capitalize() for part in slug.split())


def _first_line(text: str) -> str:
    return next((line.strip() for line in (text or "").splitlines() if line.strip()), "")


def _guess_company_from_text(job_text: str) -> str:
    first_line = _first_line(job_text)
    if first_line:
        match = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.\- ]{1,60}?)(?:[.,]|$)", first_line)
        if match:
            return _clean_whitespace(match.group(1).rstrip("."))
    for line in (job_text or "").splitlines()[:8]:
        line = line.strip()
        if not line or len(line.split()) > 6:
            continue
        if re.search(r"[A-Z]", line):
            return line
    return ""


def _match_company_job(application: dict[str, Any], jobs_catalog: list[dict[str, Any]]) -> tuple[str, str]:
    job_url = _clean_whitespace(str(application.get("job_url") or ""))
    title = _first_line(str(application.get("job") or ""))
    if job_url:
        for job in jobs_catalog:
            if _clean_whitespace(str(job.get("apply_url") or "")) == job_url:
                return str(job.get("company") or ""), str(job.get("title") or title)
    if title:
        matches = [job for job in jobs_catalog if _clean_whitespace(str(job.get("title") or "")) == title]
        if len(matches) == 1:
            return str(matches[0].get("company") or ""), str(matches[0].get("title") or title)
    return "", title


def _resolve_company_context(application: dict[str, Any], jobs_catalog: list[dict[str, Any]]) -> dict[str, str]:
    company, matched_title = _match_company_job(application, jobs_catalog)
    job_text = str(application.get("job") or "")
    job_url = _clean_whitespace(str(application.get("job_url") or ""))
    role_title = matched_title or _first_line(job_text) or "Selected role"
    if company:
        return {"company": company, "role_title": role_title, "job_url": job_url}

    if job_url:
        domain = _registrable_domain(_host_from_url(job_url))
        if domain and not _is_ats_domain(domain):
            company = _slug_to_name(domain.split(".")[0])
    if not company:
        company = _guess_company_from_text(job_text)
    if not company and job_url:
        parsed = urlparse(job_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        if "boards" in path_parts:
            board_index = path_parts.index("boards")
            if board_index + 1 < len(path_parts):
                company = _slug_to_name(path_parts[board_index + 1])
        elif path_parts:
            company = _slug_to_name(path_parts[0])
    return {"company": company or "Target company", "role_title": role_title, "job_url": job_url}


@lru_cache(maxsize=64)
def _search_duckduckgo(query: str, max_results: int = 8) -> list[dict[str, str]]:
    response = httpx.get(
        SEARCH_URL,
        params={"q": query},
        headers=HTTP_HEADERS,
        timeout=20.0,
        follow_redirects=True,
        trust_env=False,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        title = _clean_whitespace(anchor.get_text(" ", strip=True))
        url = _unwrap_duckduckgo_url(str(anchor["href"]))
        if not title or not url.startswith("http"):
            continue
        domain = _registrable_domain(_host_from_url(url))
        if url in seen:
            continue
        seen.add(url)
        results.append({"title": title, "url": url, "domain": domain})
        if len(results) >= max_results:
            break
    return results


@lru_cache(maxsize=96)
def _fetch_page_text(url: str) -> dict[str, str]:
    response = httpx.get(
        url,
        headers=HTTP_HEADERS,
        timeout=20.0,
        follow_redirects=True,
        trust_env=False,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = _clean_whitespace(soup.title.get_text(" ", strip=True) if soup.title else url)
    text = _clean_whitespace(soup.get_text(" ", strip=True))
    return {
        "title": title,
        "url": url,
        "domain": _registrable_domain(_host_from_url(url)),
        "text": text[:16000],
    }


def _official_site_from_search(company: str) -> str:
    for result in _search_duckduckgo(f"{company} official site careers", max_results=8):
        domain = result["domain"]
        if not domain or any(domain.endswith(item) for item in EXCLUDED_SEARCH_DOMAINS + COMMUNITY_DOMAINS):
            continue
        return _base_url(result["url"])
    return ""


def _collect_live_research(context: dict[str, str]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    company = context["company"]
    job_url = context["job_url"]
    official_site = ""
    if job_url:
        domain = _registrable_domain(_host_from_url(job_url))
        if domain and not _is_ats_domain(domain) and not any(domain.endswith(item) for item in COMMUNITY_DOMAINS):
            official_site = _base_url(job_url)
    if not official_site:
        official_site = _official_site_from_search(company)

    pages_to_fetch: list[tuple[str, str]] = []
    source_links: list[dict[str, str]] = []

    if job_url:
        pages_to_fetch.append(("Job advert", job_url))
        source_links.append({"title": "Job advert", "url": job_url, "source_type": "job_advert", "domain": _registrable_domain(_host_from_url(job_url))})

    if official_site:
        for suffix, title in (
            ("", "Official company page"),
            ("/careers", "Careers page"),
            ("/about", "About page"),
            ("/values", "Values page"),
            ("/engineering", "Engineering page"),
        ):
            pages_to_fetch.append((title, official_site.rstrip("/") + suffix))

        for result in _search_duckduckgo(f"site:{_host_from_url(official_site)} interview process {company}", max_results=6):
            if result["domain"] == _registrable_domain(_host_from_url(official_site)):
                pages_to_fetch.append(("Interview process page", result["url"]))

        for result in _search_duckduckgo(f"site:{_host_from_url(official_site)} careers values engineering {company}", max_results=6):
            if result["domain"] == _registrable_domain(_host_from_url(official_site)):
                pages_to_fetch.append(("Culture or engineering page", result["url"]))

    community_results = _search_duckduckgo(f"{company} engineering interview reddit indeed", max_results=8)
    for result in community_results:
        domain = result["domain"]
        if not any(domain.endswith(item) for item in COMMUNITY_DOMAINS):
            continue
        source_links.append(
            {
                "title": result["title"],
                "url": result["url"],
                "source_type": "public_interview_report",
                "domain": domain,
            }
        )
        if len([item for item in source_links if item["source_type"] == "public_interview_report"]) >= 3:
            break

    fetched_pages: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for source_title, url in pages_to_fetch:
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        try:
            page = _fetch_page_text(url)
        except Exception:
            continue
        if len(page["text"]) < 240:
            continue
        page["source_title"] = source_title
        fetched_pages.append(page)
        source_links.append(
            {
                "title": page["title"],
                "url": page["url"],
                "source_type": "official_process" if "interview" in page["title"].lower() or "interview" in page["text"].lower() else "official_company",
                "domain": page["domain"],
            }
        )
        if len(fetched_pages) >= 6:
            break

    deduped_links: list[dict[str, str]] = []
    seen_link_urls: set[str] = set()
    for item in source_links:
        if item["url"] in seen_link_urls:
            continue
        seen_link_urls.add(item["url"])
        deduped_links.append(item)
    return fetched_pages, deduped_links[:8]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text or "")
    return [_clean_whitespace(part) for part in parts if _clean_whitespace(part)]


def _extract_process_stages(job_text: str, pages: list[dict[str, str]], profile: str) -> list[PrepStage]:
    stages: list[PrepStage] = []
    seen: set[str] = set()
    for stage_name, keywords in PROCESS_STAGE_HINTS:
        for page in pages:
            for sentence in _sentences(page["text"]):
                lowered = sentence.lower()
                if not any(keyword in lowered for keyword in keywords):
                    continue
                if stage_name in seen:
                    break
                stages.append(
                    PrepStage(
                        name=stage_name,
                        detail=sentence[:240],
                        confidence="Official source",
                        source_title=page["title"],
                        source_url=page["url"],
                    )
                )
                seen.add(stage_name)
                break

    if stages:
        return stages[:5]

    profile_lower = (profile or "").lower()
    if "software" in profile_lower:
        inferred = [
            ("Recruiter screen", "Expect an initial screen on motivation, impact, and how your experience fits the role."),
            ("Technical deep dive", "Expect detailed questions on your strongest projects, code decisions, testing, and trade-offs."),
            ("Assessment or task", "Many software teams include a coding, debugging, or system design exercise."),
            ("Final panel", "Expect a final behavioural or values round focused on collaboration, ownership, and communication."),
        ]
    else:
        inferred = [
            ("Recruiter screen", "Expect an initial conversation on motivation, logistics, and why this company and role fit."),
            ("Technical deep dive", "Expect a project walkthrough on the tools you used, your decisions, and the engineering result."),
            ("Assessment or task", "Engineering employers often use a problem-solving exercise, case, or design review."),
            ("Final panel", "Expect behavioural questions on teamwork, ownership, quality, and communication."),
        ]
    return [
        PrepStage(
            name=name,
            detail=detail,
            confidence="Inferred from role and job advert",
            source_title="Role inference",
            source_url="",
        )
        for name, detail in inferred
    ]


def _extract_company_signals(company: str, pages: list[dict[str, str]], job_text: str) -> list[PrepSignal]:
    signals: list[PrepSignal] = []
    seen_titles: set[str] = set()
    for title, keywords in SIGNAL_HINTS.items():
        for page in pages:
            for sentence in _sentences(page["text"]):
                lowered = sentence.lower()
                if any(keyword in lowered for keyword in keywords):
                    if title in seen_titles:
                        break
                    signals.append(
                        PrepSignal(
                            title=title,
                            detail=sentence[:240],
                            source_title=page["title"],
                            source_url=page["url"],
                        )
                    )
                    seen_titles.add(title)
                    break
    if signals:
        return signals[:4]

    fallback_sentences = _sentences(job_text)[:4]
    fallback_titles = ["Role fit", "Technical depth", "Communication", "Delivery mindset"]
    for title, sentence in zip(fallback_titles, fallback_sentences):
        signals.append(
            PrepSignal(
                title=title,
                detail=sentence[:220],
                source_title=f"{company} job advert",
                source_url="",
            )
        )
    return signals[:4]


def _signal_question(signal: PrepSignal, company: str) -> PrepQuestion:
    lowered = signal.title.lower()
    if "customer" in lowered:
        question = f"Tell me about a time you changed an engineering decision because of a user or customer need at the centre of the problem."
    elif "ownership" in lowered:
        question = f"Describe a time you took ownership of a problem without being asked and drove it to a usable outcome."
    elif "speed" in lowered:
        question = f"Tell me about a time you delivered under ambiguity or time pressure without losing sound judgement."
    elif "quality" in lowered:
        question = f"Describe a time you protected quality, safety, or reliability when there was pressure to move faster."
    elif "learning" in lowered:
        question = f"Tell me about a time you had to learn a tool, concept, or domain quickly to unblock delivery."
    else:
        question = f"Tell me about a time you worked across functions or stakeholders to get an engineering result over the line."
    return PrepQuestion(
        question=question,
        why=f"This company signal was picked up from public company material linked to {company}.",
        anchor=signal.detail,
    )


def _weak_requirements(application: dict[str, Any]) -> list[dict[str, Any]]:
    items = application.get("requirement_evidence") or []
    if not isinstance(items, list):
        return []
    return [item for item in items if str(item.get("status") or "") in {"missing", "cover_only", "weak"}]


def _question_groups(application: dict[str, Any], company: str, signals: list[PrepSignal]) -> list[PrepQuestionGroup]:
    signal_questions = [_signal_question(signal, company) for signal in signals[:3]]
    requirement_questions = [
        PrepQuestion(
            question=f"Walk me through your strongest example of {item.get('requirement')}. What did you do personally, and what was the outcome?",
            why=f"This requirement is currently marked as {str(item.get('status') or '').replace('_', ' ')} in your review.",
            anchor=(item.get("target_line") or "Target requirement from the advert"),
        )
        for item in _weak_requirements(application)[:4]
    ]
    cv_defence_questions = [
        PrepQuestion(
            question=str(question),
            why="This came from the reviewer's interview handoff based on your CV, cover letter, and requirement gaps.",
            anchor="Grounded in your reviewed application",
        )
        for question in (application.get("interview_questions") or [])[:4]
        if str(question).strip()
    ]
    motivation_question = PrepQuestion(
        question=f"Why {company}, and why this role now rather than a broader graduate or engineering option?",
        why="This is the most likely motivation question after company-specific research.",
        anchor="Use your actual reasons, not generic enthusiasm.",
    )
    return [
        PrepQuestionGroup(
            title="Company-specific questions",
            description="These are shaped by the public signals and culture language found for this company.",
            questions=(signal_questions or [motivation_question])[:4],
        ),
        PrepQuestionGroup(
            title="Technical and role-specific questions",
            description="These target the advert requirements that matter most for interview depth.",
            questions=(requirement_questions or [motivation_question])[:4],
        ),
        PrepQuestionGroup(
            title="CV defence questions",
            description="These are the questions most likely to probe the claims and gaps in your reviewed application.",
            questions=(cv_defence_questions or [motivation_question])[:4],
        ),
    ]


def _questions_to_ask_them(company: str, signals: list[PrepSignal], stages: list[PrepStage]) -> list[str]:
    prompts = [
        f"What does strong performance in the first six months look like for this role at {company}?",
        "Which part of the interview process is meant to test day-to-day success in the role most directly?",
    ]
    if signals:
        prompts.append(f"Your public material emphasises {signals[0].title.lower()}. What does that look like in daily engineering decisions here?")
    if stages:
        prompts.append(f"I noticed a likely stage around {stages[0].name.lower()}. What does strong preparation for that stage look like?")
    return prompts[:4]


def _prep_priorities(application: dict[str, Any], signals: list[PrepSignal], stages: list[PrepStage]) -> list[str]:
    priorities: list[str] = []
    weak = _weak_requirements(application)
    if weak:
        priorities.append(f"Prepare one strong, quantified example for {weak[0].get('requirement')} before the interview.")
    if signals:
        priorities.append(f"Build one answer that shows {signals[0].title.lower()} in a way that fits this company's public signals.")
    if stages:
        priorities.append(f"Practice for the likely {stages[0].name.lower()} stage using your own projects rather than generic examples.")
    priorities.append("Keep your answers tight: context, what you owned, the decision you made, and the result.")
    return priorities[:4]


def _source_dicts(items: list[dict[str, str]]) -> list[dict[str, str]]:
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        url = item.get("url") or ""
        if not url or url in seen:
            continue
        seen.add(url)
        deduped.append(asdict(PrepSource(**item)))
    return deduped[:8]


def build_interview_prep(application: dict[str, Any], jobs_catalog: list[dict[str, Any]], live_research: bool = True) -> dict[str, Any]:
    context = _resolve_company_context(application, jobs_catalog)
    company = context["company"]
    role_title = context["role_title"]
    job_text = str(application.get("job") or "")
    profile = str(application.get("profile") or "")

    pages: list[dict[str, str]] = []
    sources: list[dict[str, str]] = []
    research_mode = "fallback"

    if live_research:
        try:
            pages, sources = _collect_live_research(context)
            research_mode = "live" if pages else "fallback"
        except Exception:
            pages, sources = [], []
            research_mode = "fallback"

    if not sources:
        job_url = context["job_url"]
        if job_url:
            sources.append(
                {
                    "title": "Job advert",
                    "url": job_url,
                    "source_type": "job_advert",
                    "domain": _registrable_domain(_host_from_url(job_url)),
                }
            )

    stages = _extract_process_stages(job_text, pages, profile)
    signals = _extract_company_signals(company, pages, job_text)
    groups = _question_groups(application, company, signals)
    ask_them = _questions_to_ask_them(company, signals, stages)
    priorities = _prep_priorities(application, signals, stages)

    summary_parts = []
    if research_mode == "live" and any(stage.confidence == "Official source" for stage in stages):
        summary_parts.append(f"Found public interview-process clues for {company} and turned them into a likely stage flow.")
    elif research_mode == "live":
        summary_parts.append(f"Found public company material for {company}, but no fully explicit interview process page.")
    else:
        summary_parts.append("No explicit public interview-process page was confirmed in this pass.")
    summary_parts.append("Questions below are grounded in the role, your reviewed application, and the company signals that were found.")

    return {
        "company": company,
        "role_title": role_title,
        "research_mode": research_mode,
        "research_confidence": (
            "High" if any(stage.confidence == "Official source" for stage in stages)
            else "Medium" if research_mode == "live"
            else "Low"
        ),
        "summary": " ".join(summary_parts),
        "process_stages": [asdict(item) for item in stages],
        "company_signals": [asdict(item) for item in signals],
        "question_groups": [
            {
                "title": group.title,
                "description": group.description,
                "questions": [asdict(question) for question in group.questions],
            }
            for group in groups
        ],
        "questions_to_ask": ask_them,
        "prep_priorities": priorities,
        "sources": _source_dicts(sources),
    }
