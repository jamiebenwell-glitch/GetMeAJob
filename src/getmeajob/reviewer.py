from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "a",
    "about",
    "above",
    "across",
    "after",
    "again",
    "against",
    "all",
    "allow",
    "along",
    "already",
    "also",
    "although",
    "always",
    "am",
    "an",
    "and",
    "any",
    "are",
    "around",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "do",
    "each",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "he",
    "her",
    "here",
    "hers",
    "him",
    "his",
    "how",
    "however",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "may",
    "might",
    "more",
    "most",
    "must",
    "need",
    "needed",
    "needs",
    "no",
    "not",
    "now",
    "of",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "out",
    "over",
    "own",
    "role",
    "roles",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "will",
    "with",
    "within",
    "work",
    "working",
    "would",
    "you",
    "your",
}

KEEP_SHORT = {"cad", "cfd", "fem", "plc", "sap", "sql", "api", "iso"}
GENERIC_TERMS = {
    "application",
    "applications",
    "candidate",
    "candidates",
    "company",
    "experience",
    "individual",
    "opportunity",
    "responsibilities",
    "responsibility",
    "skills",
    "support",
    "team",
    "teams",
}

IMPACT_VERBS = {
    "achieved",
    "automated",
    "built",
    "created",
    "delivered",
    "designed",
    "drove",
    "improved",
    "increased",
    "launched",
    "led",
    "optimized",
    "reduced",
    "solved",
    "streamlined",
}

ROLE_FAMILY_HINTS: dict[str, set[str]] = {
    "software": {
        "api",
        "backend",
        "cloud",
        "developer",
        "devops",
        "frontend",
        "full-stack",
        "fullstack",
        "java",
        "javascript",
        "microservices",
        "node",
        "python",
        "react",
        "software",
    },
    "mechanical": {
        "cad",
        "cfd",
        "fem",
        "manufacturing",
        "mechanical",
        "prototype",
        "solidworks",
        "thermodynamics",
        "tooling",
    },
    "electrical": {
        "circuit",
        "electrical",
        "electronic",
        "embedded",
        "firmware",
        "fpga",
        "pcb",
    },
    "data": {
        "analytics",
        "data",
        "etl",
        "machine",
        "learning",
        "ml",
        "sql",
    },
    "civil": {
        "civil",
        "geotechnical",
        "infrastructure",
        "structural",
    },
}

SENIORITY_PATTERNS: list[tuple[int, tuple[str, ...]]] = [
    (4, ("principal", "staff engineer", "head of", "architect")),
    (3, ("lead", "manager", "senior manager")),
    (2, ("senior", "sr ")),
    (0, ("junior", "graduate", "entry level", "associate")),
    (-1, ("intern", "internship", "placement", "year in industry", "student", "undergraduate")),
]

EARLY_STAGE_PATTERNS = (
    "undergraduate",
    "student",
    "intern",
    "internship",
    "placement",
    "year in industry",
    "industrial placement",
    "graduate scheme",
    "final year",
)

CATEGORY_HINTS: dict[str, set[str]] = {
    "technical": {
        "analysis",
        "cad",
        "cfd",
        "design",
        "engineering",
        "fem",
        "matlab",
        "modelling",
        "simulation",
        "solidworks",
        "testing",
    },
    "manufacturing": {
        "assembly",
        "factory",
        "lean",
        "machining",
        "manufacturing",
        "production",
        "process",
        "prototype",
        "quality",
        "tooling",
    },
    "commercial": {
        "client",
        "commercial",
        "customer",
        "deadline",
        "stakeholder",
        "supplier",
    },
    "motivation": {
        "career",
        "develop",
        "enthusiasm",
        "interested",
        "learn",
        "motivation",
        "passion",
    },
}


@dataclass(frozen=True)
class ReviewScore:
    total: int
    relevance: int
    tailoring: int
    specificity: int
    structure: int
    clarity: int


@dataclass(frozen=True)
class Highlight:
    issue_id: int
    excerpt: str
    reason: str
    suggestion: str


@dataclass(frozen=True)
class RequirementCategory:
    name: str
    label: str
    keywords: list[str]
    coverage: int
    matched_keywords: list[str]
    missing_keywords: list[str]


@dataclass(frozen=True)
class ReviewResult:
    score: ReviewScore
    notes: list[str]
    keyword_overlap: list[str]
    missing_keywords: list[str]
    cv_highlights: list[Highlight]
    cover_highlights: list[Highlight]
    categories: list[RequirementCategory]


@dataclass(frozen=True)
class RoleSuggestion:
    title: str
    company: str
    location: str
    duration: str
    apply_url: str
    score: int
    matched_keywords: list[str]
    summary: str
    job_description: str


def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z\-]{1,}", text.lower())
    normalized: list[str] = []
    for token in tokens:
        if token in STOPWORDS:
            continue
        if len(token) < 4 and token not in KEEP_SHORT:
            continue
        if token in GENERIC_TERMS:
            continue
        normalized.append(token)
    return normalized


def _extract_keywords(text: str, limit: int = 14) -> list[str]:
    counts = Counter(_tokenize(text))
    ranked = sorted(counts.items(), key=lambda item: (-item[1], -len(item[0]), item[0]))
    return [word for word, _ in ranked[:limit]]


def _job_text(job: dict[str, object]) -> str:
    requirements = job.get("key_requirements") or []
    if isinstance(requirements, list):
        requirements_text = " ".join(str(item) for item in requirements)
    else:
        requirements_text = str(requirements)
    return " ".join(
        str(
            value or ""
        )
        for value in [
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("department"),
            job.get("summary"),
            requirements_text,
        ]
    )


def _extract_company_name(job_text: str) -> str | None:
    match = re.search(r"(?i)company[:\s]+([A-Z][A-Za-z0-9&\-. ]{2,})", job_text)
    if match:
        return match.group(1).strip()
    return None


def _extract_years_of_experience(text: str) -> int:
    matches = re.findall(r"(?i)(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)?", text)
    values = [int(match) for match in matches]
    return max(values, default=0)


def _detect_job_seniority(job_text: str) -> int:
    normalized = f" {job_text.lower()} "
    years_required = _extract_years_of_experience(job_text)
    level = 1

    for score, patterns in SENIORITY_PATTERNS:
        if any(pattern in normalized for pattern in patterns):
            level = max(level, score)

    if years_required >= 8:
        level = max(level, 4)
    elif years_required >= 5:
        level = max(level, 3)
    elif years_required >= 3:
        level = max(level, 2)
    elif years_required >= 1:
        level = max(level, 1)

    return level


def _detect_candidate_seniority(cv_text: str, cover_text: str) -> int:
    combined = f" {cv_text.lower()} {cover_text.lower()} "
    if any(pattern in combined for pattern in EARLY_STAGE_PATTERNS):
        return -1

    years = max(_extract_years_of_experience(cv_text), _extract_years_of_experience(cover_text))
    if years >= 8:
        return 4
    if years >= 5:
        return 3
    if years >= 3:
        return 2
    if years >= 1:
        return 1
    return 0


def _role_family_scores(text: str) -> dict[str, int]:
    tokens = Counter(_tokenize(text))
    scores: dict[str, int] = {}
    for family, hints in ROLE_FAMILY_HINTS.items():
        score = sum(tokens.get(hint, 0) for hint in hints)
        if score > 0:
            scores[family] = score
    return scores


def _dominant_families(text: str) -> set[str]:
    scores = _role_family_scores(text)
    if not scores:
        return set()
    top_score = max(scores.values())
    if top_score <= 1:
        return set()
    return {family for family, score in scores.items() if score == top_score}


def _fit_caps(job_text: str, cv_text: str, cover_text: str) -> tuple[int, int, list[str]]:
    notes: list[str] = []
    total_cap = 100
    relevance_cap = 100

    job_level = _detect_job_seniority(job_text)
    candidate_level = _detect_candidate_seniority(cv_text, cover_text)
    required_years = _extract_years_of_experience(job_text)
    candidate_years = max(_extract_years_of_experience(cv_text), _extract_years_of_experience(cover_text))

    if job_level >= 3 and candidate_level <= 0:
        total_cap = min(total_cap, 35)
        relevance_cap = min(relevance_cap, 30)
        notes.append("This role reads as experienced or senior, but the application reads as student or early-career.")
    elif job_level - candidate_level >= 2:
        total_cap = min(total_cap, 45)
        relevance_cap = min(relevance_cap, 40)
        notes.append("The application looks under-level for the seniority expected by this role.")

    if required_years >= 3 and candidate_years == 0 and candidate_level <= 0:
        total_cap = min(total_cap, 40)
        relevance_cap = min(relevance_cap, 35)
        notes.append(f"The advert asks for around {required_years}+ years of experience, and that evidence is missing here.")
    elif required_years >= 5 and candidate_years < max(required_years - 2, 1):
        total_cap = min(total_cap, 45)
        relevance_cap = min(relevance_cap, 40)
        notes.append("The documented years of experience appear well below the level requested in the advert.")

    job_families = _dominant_families(job_text)
    candidate_families = _dominant_families(f"{cv_text} {cover_text}")
    if job_families and candidate_families and not (job_families & candidate_families):
        total_cap = min(total_cap, 25)
        relevance_cap = min(relevance_cap, 20)
        notes.append(
            "This looks like a role-family mismatch: the advert and the application point to different disciplines."
        )

    return total_cap, relevance_cap, notes


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _sentence_lengths(text: str) -> list[int]:
    sentences = re.split(r"[.!?]+", text)
    return [len(re.findall(r"\b\w+\b", s)) for s in sentences if s.strip()]


def _split_segments(text: str) -> list[str]:
    raw_segments = re.split(r"\n+|(?<=[.!?])\s+", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]


def _categorize_requirements(job_text: str, cv_text: str, cover_text: str) -> list[RequirementCategory]:
    job_keywords = _extract_keywords(job_text)
    document_tokens = set(_tokenize(cv_text + " " + cover_text))
    categories: list[RequirementCategory] = []
    assigned: set[str] = set()

    for name, hints in CATEGORY_HINTS.items():
        category_keywords = [keyword for keyword in job_keywords if keyword in hints]
        if not category_keywords:
            continue
        assigned.update(category_keywords)
        matched = [keyword for keyword in category_keywords if keyword in document_tokens]
        missing = [keyword for keyword in category_keywords if keyword not in document_tokens]
        coverage = int(round(100 * len(matched) / len(category_keywords))) if category_keywords else 0
        categories.append(
            RequirementCategory(
                name=name,
                label=name.capitalize(),
                keywords=category_keywords,
                coverage=coverage,
                matched_keywords=matched,
                missing_keywords=missing,
            )
        )

    remaining = [keyword for keyword in job_keywords if keyword not in assigned]
    if remaining:
        matched = [keyword for keyword in remaining if keyword in document_tokens]
        missing = [keyword for keyword in remaining if keyword not in document_tokens]
        coverage = int(round(100 * len(matched) / len(remaining)))
        categories.append(
            RequirementCategory(
                name="general",
                label="General requirements",
                keywords=remaining,
                coverage=coverage,
                matched_keywords=matched,
                missing_keywords=missing,
            )
        )

    return categories


def _score_relevance(categories: list[RequirementCategory]) -> tuple[int, list[str], list[str]]:
    if not categories:
        return 50, [], []

    all_keywords = [keyword for category in categories for keyword in category.keywords]
    matched = [keyword for category in categories for keyword in category.matched_keywords]
    missing = [keyword for category in categories for keyword in category.missing_keywords]
    score = int(round(100 * len(matched) / max(len(all_keywords), 1)))
    return max(10, min(score, 100)), matched[:12], missing[:12]


def _score_tailoring(job_text: str, cover_text: str) -> int:
    company = _extract_company_name(job_text)
    if company and company.lower() in cover_text.lower():
        return 90
    role_match = re.search(r"(?i)(role|position|title)[:\s]+(.{3,80})", job_text)
    if role_match and role_match.group(2).strip().lower() in cover_text.lower():
        return 75
    return 45


def _score_specificity(cv_text: str, cover_text: str) -> int:
    combined = cv_text + "\n" + cover_text
    numbers = len(re.findall(r"\b\d+%?\b", combined))
    impact = sum(1 for w in _tokenize(combined) if w in IMPACT_VERBS)
    score = min(100, 25 + numbers * 3 + impact * 4)
    return max(10, score)


def _score_structure(cv_text: str, cover_text: str) -> int:
    cv_words = _word_count(cv_text)
    cover_words = _word_count(cover_text)
    cv_score = 100 if 250 <= cv_words <= 850 else 60
    cover_score = 100 if 180 <= cover_words <= 450 else 60
    return int(round((cv_score + cover_score) / 2))


def _score_clarity(texts: Iterable[str]) -> int:
    lengths = []
    for text in texts:
        lengths.extend(_sentence_lengths(text))
    if not lengths:
        return 50
    avg_len = sum(lengths) / len(lengths)
    if 10 <= avg_len <= 22:
        return 90
    if 22 < avg_len <= 30:
        return 75
    return 55


def _build_highlights(text: str, categories: list[RequirementCategory], start_id: int, doc_name: str) -> list[Highlight]:
    highlights: list[Highlight] = []
    segments = _split_segments(text)
    missing_focus = [keyword for category in categories for keyword in category.missing_keywords][:4]

    for segment in segments:
        if len(highlights) >= 3:
            break

        tokens = set(_tokenize(segment))
        words = re.findall(r"\b\w+\b", segment)

        if len(words) > 35:
            highlights.append(
                Highlight(
                    issue_id=start_id + len(highlights),
                    excerpt=segment,
                    reason=f"{doc_name} sentence is too dense.",
                    suggestion="Rewrite this as two shorter points so the recruiter can scan it quickly.",
                )
            )
            continue

        if any(verb in segment.lower() for verb in IMPACT_VERBS) and not re.search(r"\b\d+%?\b", segment):
            highlights.append(
                Highlight(
                    issue_id=start_id + len(highlights),
                    excerpt=segment,
                    reason=f"{doc_name} claim lacks proof.",
                    suggestion="Add a measurable result, timescale, or scale of work here.",
                )
            )
            continue

        if missing_focus and len(words) >= 8 and not any(keyword in tokens for keyword in missing_focus):
            focus = ", ".join(missing_focus[:2])
            highlights.append(
                Highlight(
                    issue_id=start_id + len(highlights),
                    excerpt=segment,
                    reason=f"{doc_name} point is too generic for this advert.",
                    suggestion=f"Link this point to the advert more directly, for example {focus}.",
                )
            )

    return highlights


def recommend_roles(cv_text: str, jobs: list[dict[str, object]], limit: int = 5) -> list[RoleSuggestion]:
    cv_tokens = set(_tokenize(cv_text))
    if not cv_tokens:
        return []

    ranked: list[tuple[int, RoleSuggestion]] = []
    for job in jobs:
        text = _job_text(job)
        job_keywords = _extract_keywords(text, limit=18)
        if not job_keywords:
            continue

        matched = [keyword for keyword in job_keywords if keyword in cv_tokens]
        if not matched:
            continue

        title_tokens = set(_tokenize(str(job.get("title") or "")))
        requirement_tokens = set(_tokenize(" ".join(str(item) for item in (job.get("key_requirements") or []))))
        title_hits = len(title_tokens & cv_tokens)
        requirement_hits = len(requirement_tokens & cv_tokens)
        base_score = int(round(100 * len(matched) / len(job_keywords)))
        score = min(99, base_score + title_hits * 7 + requirement_hits * 2)
        total_cap, _, _ = _fit_caps(text, cv_text, "")
        score = min(score, total_cap)
        if total_cap <= 35:
            score = min(score, 15)
        elif total_cap >= 80:
            score = max(score, 25)

        suggestion = RoleSuggestion(
            title=str(job.get("title") or "Untitled role"),
            company=str(job.get("company") or "Unknown company"),
            location=str(job.get("location") or "Location not listed"),
            duration=str(job.get("duration") or "Duration not listed"),
            apply_url=str(job.get("apply_url") or ""),
            score=max(score, 10),
            matched_keywords=matched[:6],
            summary=str(job.get("summary") or ""),
            job_description=(
                f"{str(job.get('title') or '')}\n"
                f"{str(job.get('location') or '')}\n"
                f"{str(job.get('summary') or '')}\n"
                "Requirements:\n- "
                + "\n- ".join(str(item) for item in (job.get("key_requirements") or []))
            ).strip(),
        )
        ranked.append((score, suggestion))

    ranked.sort(key=lambda item: (-item[0], item[1].company, item[1].title))
    return [suggestion for _, suggestion in ranked[:limit]]


def review(job_text: str, cv_text: str, cover_text: str) -> ReviewResult:
    categories = _categorize_requirements(job_text, cv_text, cover_text)
    relevance, overlap, missing = _score_relevance(categories)
    tailoring = _score_tailoring(job_text, cover_text)
    specificity = _score_specificity(cv_text, cover_text)
    structure = _score_structure(cv_text, cover_text)
    clarity = _score_clarity([cv_text, cover_text])
    total_cap, relevance_cap, fit_notes = _fit_caps(job_text, cv_text, cover_text)

    relevance = min(relevance, relevance_cap)

    total = int(
        round(
            relevance * 0.35
            + tailoring * 0.2
            + specificity * 0.2
            + structure * 0.15
            + clarity * 0.1
        )
    )
    total = min(total, total_cap)

    notes: list[str] = list(fit_notes)
    low_categories = [category.label for category in categories if category.coverage < 50]
    if low_categories:
        notes.append(f"Strengthen weak requirement areas: {', '.join(low_categories[:3])}.")
    if tailoring < 70:
        notes.append("Tailor the cover letter with the company name and role title.")
    if specificity < 70:
        notes.append("Add quantified outcomes and stronger proof of impact.")
    if structure < 70:
        notes.append("Keep CV around 1 page and cover letter around 200-400 words.")
    if clarity < 70:
        notes.append("Shorten dense sentences so a recruiter can scan faster.")

    cv_highlights = _build_highlights(cv_text, categories, 1, "CV")
    cover_highlights = _build_highlights(cover_text, categories, 101, "Cover letter")

    return ReviewResult(
        score=ReviewScore(
            total=total,
            relevance=relevance,
            tailoring=tailoring,
            specificity=specificity,
            structure=structure,
            clarity=clarity,
        ),
        notes=notes,
        keyword_overlap=overlap,
        missing_keywords=missing,
        cv_highlights=cv_highlights,
        cover_highlights=cover_highlights,
        categories=categories,
    )


def review_from_files(job_path: str, cv_path: str, cover_path: str) -> ReviewResult:
    return review(_read_text(job_path), _read_text(cv_path), _read_text(cover_path))


def to_json(result: ReviewResult) -> str:
    payload = {
        "score": result.score.__dict__,
        "notes": result.notes,
        "keyword_overlap": result.keyword_overlap,
        "missing_keywords": result.missing_keywords,
        "cv_highlights": [highlight.__dict__ for highlight in result.cv_highlights],
        "cover_highlights": [highlight.__dict__ for highlight in result.cover_highlights],
        "categories": [category.__dict__ for category in result.categories],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
