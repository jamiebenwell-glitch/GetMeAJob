
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "a", "about", "above", "across", "after", "again", "against", "all", "allow", "along",
    "already", "also", "although", "always", "am", "an", "and", "any", "are", "around",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "could", "do", "each", "for", "from", "further", "had", "has",
    "have", "he", "her", "here", "hers", "him", "his", "how", "however", "if", "in",
    "into", "is", "it", "its", "itself", "just", "may", "might", "more", "most", "must",
    "need", "needed", "needs", "no", "not", "now", "of", "on", "once", "only", "or",
    "other", "our", "ours", "out", "over", "own", "role", "roles", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "will", "with", "within", "work", "working", "would", "you", "your",
}

KEEP_SHORT = {"cad", "cfd", "fem", "plc", "sap", "sql", "api", "iso", "qa", "ml", "ai"}
GENERIC_TERMS = {
    "application", "applications", "candidate", "candidates", "company", "experience", "individual",
    "opportunity", "responsibilities", "responsibility", "skills", "support", "team", "teams",
    "graduate", "placement", "internship", "industry", "year", "analyst", "apprentice",
}

IMPACT_VERBS = {
    "achieved", "automated", "built", "created", "delivered", "designed", "developed", "drove",
    "improved", "increased", "launched", "led", "optimized", "reduced", "solved", "streamlined",
}

ROLE_FAMILY_HINTS: dict[str, set[str]] = {
    "software": {"api", "backend", "cloud", "developer", "devops", "frontend", "full-stack", "fullstack", "java", "javascript", "microservices", "node", "python", "react", "software"},
    "mechanical": {"cad", "cfd", "fem", "lean", "manufacturing", "mechanical", "prototype", "solidworks", "thermodynamics", "tooling"},
    "electrical": {"circuit", "electrical", "electronic", "embedded", "firmware", "fpga", "pcb"},
    "data": {"analytics", "dashboard", "data", "etl", "machine", "learning", "ml", "sql"},
    "civil": {"civil", "geotechnical", "infrastructure", "structural"},
}

SENIORITY_PATTERNS: list[tuple[int, tuple[str, ...]]] = [
    (4, ("principal", "staff engineer", "head of", "architect")),
    (3, ("lead", "manager", "senior manager")),
    (2, ("senior", "sr ")),
    (0, ("junior", "graduate", "entry level", "associate")),
    (-1, ("intern", "internship", "placement", "year in industry", "student", "undergraduate")),
]

EARLY_STAGE_PATTERNS = (
    "undergraduate", "student", "intern", "internship", "placement", "year in industry",
    "industrial placement", "graduate scheme", "final year",
)

EARLY_ROLE_PATTERNS = (
    "undergraduate", "student", "intern", "internship", "placement", "year in industry",
    "industrial placement", "graduate", "graduate scheme", "entry level", "junior", "apprentice",
)

CATEGORY_HINTS: dict[str, set[str]] = {
    "technical": {"analysis", "api", "backend", "cad", "cfd", "cloud", "controls", "design", "embedded", "engineering", "fem", "firmware", "frontend", "matlab", "modelling", "python", "react", "simulation", "software", "solidworks", "testing"},
    "manufacturing": {"assembly", "factory", "lean", "machining", "manufacturing", "production", "process", "prototype", "quality", "safety", "tooling", "validation"},
    "commercial": {"client", "commercial", "communication", "customer", "deadline", "project_management", "stakeholder", "supplier"},
    "motivation": {"career", "develop", "enthusiasm", "interested", "learn", "motivation", "passion"},
}
CONCEPT_SYNONYMS: dict[str, set[str]] = {
    "analysis": {"analysis", "analytical", "analyse", "analyze", "investigation"},
    "api": {"api", "apis", "rest api", "restful api", "integration"},
    "assembly": {"assembly", "integration build"},
    "automation": {"automation", "automated"},
    "autonomy": {"autonomy", "autonomous"},
    "backend": {"backend", "server-side", "services", "service development"},
    "cad": {"cad", "catia", "creo", "solidworks", "nx", "autocad"},
    "cfd": {"cfd", "computational fluid dynamics"},
    "cloud": {"aws", "azure", "cloud", "gcp", "kubernetes"},
    "communication": {"communicate", "communication", "presented", "presentation"},
    "controls": {"control", "controls", "control systems"},
    "customer": {"customer", "client", "user-facing", "end user"},
    "data": {"data", "dataset", "datasets", "report", "reporting", "reports", "dashboard", "dashboards"},
    "design": {"design", "designed", "designing"},
    "distributed_systems": {"distributed systems", "distributed system", "scalable systems", "scalable services", "microservices"},
    "electrical": {"electrical", "electronics", "electronic"},
    "embedded": {"embedded", "microcontroller", "real-time systems"},
    "engineering": {"engineering", "engineer"},
    "fem": {"fea", "fem", "finite element"},
    "field": {"field engineer", "field service", "onsite"},
    "firmware": {"firmware", "low-level software"},
    "frontend": {"frontend", "front-end", "ui"},
    "hardware": {"hardware", "electromechanical"},
    "java": {"java"},
    "leadership": {"lead", "led", "leadership", "mentor", "mentored", "mentoring"},
    "lean": {"lean", "continuous improvement", "kaizen"},
    "machine_learning": {"ai", "machine learning", "ml"},
    "manufacturing": {"manufacturing", "production", "industrialisation", "industrialization"},
    "matlab": {"matlab", "simulink"},
    "mechanical": {"mechanical", "mechanics", "mechanism"},
    "modelling": {"modeling", "modelling", "models", "simulation models"},
    "plc": {"plc", "programmable logic controller"},
    "process": {"process", "process improvement", "production support", "continuous improvement", "lean improvement"},
    "project_management": {"project management", "programme management", "program management", "delivery planning"},
    "prototype": {"prototype", "prototyping"},
    "python": {"python"},
    "quality": {"quality", "qa", "quality assurance"},
    "react": {"react"},
    "robotics": {"robot", "robotics"},
    "safety": {"safety", "safe systems"},
    "simulation": {"simulation", "simulations", "simulate"},
    "software": {"software", "application development"},
    "sql": {"sql", "postgres", "mysql"},
    "stakeholder": {"stakeholder", "stakeholders", "cross-functional", "cross functional"},
    "testing": {"test", "testing", "verification", "validation", "v&v"},
    "tooling": {"tooling", "fixtures", "jigs"},
}

REQUIREMENT_PRIORITY_HINTS: list[tuple[float, tuple[str, ...], str]] = [
    (1.35, ("must", "required", "essential", "minimum", "proven", "track record", "expertise in"), "hard"),
    (0.75, ("preferred", "desirable", "nice to have", "bonus", "plus"), "preferred"),
    (0.95, ("you will", "you'll", "responsible for", "deliver", "build", "own"), "responsibility"),
]

TITLE_CONCEPT_BOOST = 1.2
TITLE_TOKEN_BOOST = 0.9
MIN_RELEVANCE_FLOOR = 18
MATCH_DISPLAY_THRESHOLD = 0.05


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
class RequirementEvidence:
    requirement: str
    priority: str
    status: str
    cv_evidence: list[str]
    cover_evidence: list[str]
    target_line: str


@dataclass(frozen=True)
class ReviewVerdict:
    label: str
    confidence: str
    rationale: str


@dataclass(frozen=True)
class AtsCheck:
    name: str
    status: str
    note: str


@dataclass(frozen=True)
class AtsDiagnostics:
    score: int
    checks: list["AtsCheck"]


@dataclass(frozen=True)
class ReviewResult:
    score: ReviewScore
    profile: str
    verdict: ReviewVerdict
    notes: list[str]
    keyword_overlap: list[str]
    missing_keywords: list[str]
    cv_highlights: list[Highlight]
    cover_highlights: list[Highlight]
    tailored_advice: list["TailoredAdvice"]
    requirement_evidence: list["RequirementEvidence"]
    ats_diagnostics: AtsDiagnostics
    follow_up_questions: list[str]
    interview_questions: list[str]
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


@dataclass(frozen=True)
class TailoredAdvice:
    source: str
    reason: str
    excerpt: str
    suggestion: str
    target_requirements: list[str]


@dataclass(frozen=True)
class RequirementSignal:
    concept: str
    weight: float
    priority: str
    source_line: str


CONCEPT_INDEX = {
    synonym: concept for concept, synonyms in CONCEPT_SYNONYMS.items() for synonym in sorted(synonyms, key=len, reverse=True)
}

def _read_text(path: str | Path) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def _normalize_text(text: str) -> str:
    normalized = (text or "").lower()
    replacements = {
        "c++": " cpp ",
        "c#": " csharp ",
        ".net": " dotnet ",
        "node.js": " nodejs ",
        "full stack": " full-stack ",
        "front end": " frontend ",
        "back end": " backend ",
        "year-in-industry": " year in industry ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"\s+", " ", normalized)


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9#+\-/.]{1,}", _normalize_text(text))
    normalized: list[str] = []
    for token in tokens:
        token = token.strip(".-/ ")
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


def _extract_concepts(text: str) -> Counter[str]:
    normalized = f" {_normalize_text(text)} "
    concepts: Counter[str] = Counter()
    for concept, synonyms in CONCEPT_SYNONYMS.items():
        for synonym in sorted(synonyms, key=len, reverse=True):
            if " " in synonym or "-" in synonym:
                pattern = re.escape(synonym)
            else:
                pattern = rf"\b{re.escape(synonym)}\b"
            matches = re.findall(pattern, normalized)
            if matches:
                concepts[concept] += len(matches)
    return concepts


def _concept_label(concept: str) -> str:
    return concept.replace("_", " ")


def _job_text(job: dict[str, object]) -> str:
    requirements = job.get("key_requirements") or []
    if isinstance(requirements, list):
        requirements_text = " ".join(str(item) for item in requirements)
    else:
        requirements_text = str(requirements)
    return " ".join(
        str(value or "")
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


def _is_early_career_role(job_text: str) -> bool:
    normalized = f" {_normalize_text(job_text)} "
    return any(pattern in normalized for pattern in EARLY_ROLE_PATTERNS)


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
    elif job_level >= 2 and job_level - candidate_level >= 2:
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
        total_cap = min(total_cap, 28)
        relevance_cap = min(relevance_cap, 22)
        notes.append("This looks like a role-family mismatch: the advert and the application point to different disciplines.")
    return total_cap, relevance_cap, notes


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _sentence_lengths(text: str) -> list[int]:
    sentences = re.split(r"[.!?]+", text)
    return [len(re.findall(r"\b\w+\b", s)) for s in sentences if s.strip()]


def _split_segments(text: str) -> list[str]:
    raw_segments = re.split(r"\n+|(?<=[.!?])\s+", text)
    return [segment.strip() for segment in raw_segments if segment.strip()]

def _line_priority(line: str) -> tuple[float, str]:
    lowered = line.lower()
    for weight, markers, label in REQUIREMENT_PRIORITY_HINTS:
        if any(marker in lowered for marker in markers):
            return weight, label
    return 0.9, "context"


def _extract_requirement_signals(job_text: str) -> list[RequirementSignal]:
    signals: list[RequirementSignal] = []
    seen: set[tuple[str, str]] = set()
    segments = _split_segments(job_text)
    title = segments[0] if segments else job_text
    title_concepts = _extract_concepts(title)
    for concept in title_concepts:
        signals.append(RequirementSignal(concept=concept, weight=TITLE_CONCEPT_BOOST, priority="title", source_line=title.strip()))
        seen.add((concept, title.strip()))

    for token in _extract_keywords(title, limit=5):
        concept = CONCEPT_INDEX.get(token)
        if concept or token in GENERIC_TERMS or token in STOPWORDS:
            continue
        pair = (token, title.strip())
        if pair in seen:
            continue
        signals.append(RequirementSignal(concept=token, weight=TITLE_TOKEN_BOOST, priority="title", source_line=title.strip()))
        seen.add(pair)

    for line in _split_segments(job_text):
        if _word_count(line) < 4:
            continue
        weight, priority = _line_priority(line)
        concepts = _extract_concepts(line)
        if concepts:
            for concept, count in concepts.items():
                pair = (concept, line)
                if pair in seen:
                    continue
                signals.append(
                    RequirementSignal(
                        concept=concept,
                        weight=weight + min(0.25, 0.08 * max(count - 1, 0)),
                        priority=priority,
                        source_line=line,
                    )
                )
                seen.add(pair)
            continue

        for token in _extract_keywords(line, limit=4):
            if token in GENERIC_TERMS:
                continue
            pair = (token, line)
            if pair in seen:
                continue
            signals.append(RequirementSignal(concept=token, weight=max(0.55, weight - 0.15), priority=priority, source_line=line))
            seen.add(pair)
    return signals


def _category_for_concept(concept: str) -> str:
    for category, hints in CATEGORY_HINTS.items():
        if concept in hints:
            return category
    return "general"


def _build_requirement_map(job_text: str) -> dict[str, RequirementSignal]:
    aggregated: dict[str, RequirementSignal] = {}
    for signal in _extract_requirement_signals(job_text):
        current = aggregated.get(signal.concept)
        if current is None or signal.weight > current.weight:
            aggregated[signal.concept] = signal
    return aggregated


def _candidate_concept_strength(text: str, *, cover_bonus: float = 0.0) -> dict[str, float]:
    strengths: defaultdict[str, float] = defaultdict(float)
    segment_counts: defaultdict[str, int] = defaultdict(int)

    for segment in _split_segments(text):
        concepts = _extract_concepts(segment)
        if not concepts:
            continue

        evidence = 0.38 + cover_bonus
        if re.search(r"\b\d+(?:%|x|\+)?\b", segment):
            evidence += 0.22
        if any(verb in segment.lower() for verb in IMPACT_VERBS):
            evidence += 0.18
        if any(marker in segment.lower() for marker in ("led", "managed", "owned", "delivered", "improved")):
            evidence += 0.08
        evidence = min(0.96, evidence)

        for concept, count in concepts.items():
            segment_counts[concept] += 1
            strengths[concept] = max(strengths[concept], evidence + min(0.08, 0.03 * max(count - 1, 0)))

    for concept, count in segment_counts.items():
        if count > 1:
            strengths[concept] = min(1.0, strengths[concept] + min(0.12, 0.04 * (count - 1)))
    return dict(strengths)


def _candidate_profile(cv_text: str, cover_text: str) -> dict[str, float]:
    cv_profile = _candidate_concept_strength(cv_text, cover_bonus=0.0)
    cover_profile = _candidate_concept_strength(cover_text, cover_bonus=-0.04)
    profile = dict(cv_profile)
    for concept, strength in cover_profile.items():
        if concept in cv_profile:
            profile[concept] = max(profile.get(concept, 0.0), strength)
        else:
            profile[concept] = max(profile.get(concept, 0.0), strength * 0.68)
    return profile


def _coverage_strength(evidence: float) -> float:
    if evidence <= 0:
        return 0.0
    return min(1.0, 0.55 + 0.45 * evidence)


def _categorize_requirements(job_text: str, cv_text: str, cover_text: str) -> list[RequirementCategory]:
    requirements = _build_requirement_map(job_text)
    evidence = _candidate_profile(cv_text, cover_text)
    grouped: dict[str, list[RequirementSignal]] = defaultdict(list)
    for signal in requirements.values():
        grouped[_category_for_concept(signal.concept)].append(signal)

    categories: list[RequirementCategory] = []
    for name in [key for key in CATEGORY_HINTS] + ["general"]:
        signals = grouped.get(name, [])
        if not signals:
            continue
        total_weight = sum(signal.weight for signal in signals)
        matched_weight = sum(signal.weight * _coverage_strength(evidence.get(signal.concept, 0.0)) for signal in signals)
        matched = [_concept_label(signal.concept) for signal in signals if evidence.get(signal.concept, 0.0) > MATCH_DISPLAY_THRESHOLD]
        missing = [_concept_label(signal.concept) for signal in signals if evidence.get(signal.concept, 0.0) <= MATCH_DISPLAY_THRESHOLD]
        coverage = int(round(100 * matched_weight / max(total_weight, 0.01)))
        categories.append(
            RequirementCategory(
                name=name,
                label="General requirements" if name == "general" else name.capitalize(),
                keywords=[_concept_label(signal.concept) for signal in signals],
                coverage=max(0, min(coverage, 100)),
                matched_keywords=matched[:8],
                missing_keywords=missing[:8],
            )
        )
    return categories

def _score_relevance(job_text: str, cv_text: str, cover_text: str, categories: list[RequirementCategory]) -> tuple[int, list[str], list[str]]:
    requirements = _build_requirement_map(job_text)
    evidence = _candidate_profile(cv_text, cover_text)
    if not requirements:
        return 55, [], []

    total_weight = sum(signal.weight for signal in requirements.values())
    matched_weight = sum(signal.weight * _coverage_strength(evidence.get(signal.concept, 0.0)) for signal in requirements.values())
    score = int(round(100 * matched_weight / max(total_weight, 0.01)))

    job_families = _dominant_families(job_text)
    candidate_families = _dominant_families(f"{cv_text} {cover_text}")
    if job_families and candidate_families and job_families & candidate_families:
        score += 8
    elif job_families and candidate_families and not (job_families & candidate_families):
        score -= 15

    title_segments = _split_segments(job_text)
    title_text = title_segments[0] if title_segments else job_text
    title_keywords = _extract_keywords(title_text, limit=6)
    matched_title = sum(1 for token in title_keywords if token in _tokenize(cv_text + " " + cover_text))
    score += min(10, matched_title * 3)

    matched = []
    missing = []
    sorted_requirements = sorted(requirements.values(), key=lambda item: (-item.weight, item.concept))
    for signal in sorted_requirements:
        label = _concept_label(signal.concept)
        if evidence.get(signal.concept, 0.0) > MATCH_DISPLAY_THRESHOLD:
            if label not in matched:
                matched.append(label)
        else:
            if label not in missing:
                missing.append(label)

    if score > 0 and matched:
        score = max(MIN_RELEVANCE_FLOOR, score)
    return max(8, min(score, 100)), matched[:12], missing[:12]


def _score_tailoring(job_text: str, cv_text: str, cover_text: str) -> int:
    score = 42
    cover_lower = cover_text.lower()
    company = _extract_company_name(job_text)
    if company and company.lower() in cover_lower:
        score += 18

    title_segments = _split_segments(job_text)
    title = title_segments[0] if title_segments else job_text
    title_keywords = [token for token in _extract_keywords(title, limit=8) if token not in GENERIC_TERMS]
    echoed_title = sum(1 for token in title_keywords if token in _tokenize(cover_text))
    score += min(16, echoed_title * 4)

    high_priority = sorted(_build_requirement_map(job_text).values(), key=lambda item: (-item.weight, item.concept))[:5]
    cover_concepts = _extract_concepts(cover_text)
    echoed_requirements = sum(1 for signal in high_priority if cover_concepts.get(signal.concept, 0) > 0)
    score += min(18, echoed_requirements * 4)

    if any(word in cover_lower for word in ("interested", "motivation", "why", "because", "excited")):
        score += 6
    if re.search(r"\b\d+(?:%|x|\+)?\b", cover_text):
        score += 6

    cv_concepts = _extract_concepts(cv_text)
    if company and company.lower() in cv_text.lower() and company.lower() in cover_lower:
        score += 4
    if not cover_concepts and not cv_concepts:
        score = min(score, 40)
    return max(20, min(score, 95))


def _score_specificity(cv_text: str, cover_text: str) -> int:
    combined = cv_text + "\n" + cover_text
    numbers = len(re.findall(r"\b\d+(?:%|x|\+)?\b", combined))
    impact = sum(1 for w in _tokenize(combined) if w in IMPACT_VERBS)
    concrete_concepts = len(_extract_concepts(combined))
    score = 28 + numbers * 4 + impact * 5 + concrete_concepts * 2
    return max(12, min(score, 100))


def _score_structure(cv_text: str, cover_text: str) -> int:
    cv_words = _word_count(cv_text)
    cover_words = _word_count(cover_text)
    if 220 <= cv_words <= 900:
        cv_score = 96
    elif 80 <= cv_words < 220:
        cv_score = 82
    else:
        cv_score = 62

    if 140 <= cover_words <= 500:
        cover_score = 92
    elif 60 <= cover_words < 140:
        cover_score = 78
    else:
        cover_score = 64
    return int(round((cv_score + cover_score) / 2))


def _score_clarity(texts: Iterable[str]) -> int:
    lengths = []
    for text in texts:
        lengths.extend(_sentence_lengths(text))
    if not lengths:
        return 50
    avg_len = sum(lengths) / len(lengths)
    if 9 <= avg_len <= 22:
        return 90
    if 22 < avg_len <= 30:
        return 75
    return 55


def _high_priority_missing(job_text: str, cv_text: str, cover_text: str, limit: int = 4) -> list[str]:
    requirements = sorted(_build_requirement_map(job_text).values(), key=lambda item: (-item.weight, item.concept))
    evidence = _candidate_profile(cv_text, cover_text)
    missing: list[str] = []
    for signal in requirements:
        if evidence.get(signal.concept, 0.0) > MATCH_DISPLAY_THRESHOLD:
            continue
        label = _concept_label(signal.concept)
        if label not in missing:
            missing.append(label)
        if len(missing) >= limit:
            break
    return missing


def _cover_only_requirement_gaps(job_text: str, cv_text: str, cover_text: str, limit: int = 5) -> list[str]:
    requirements = sorted(_build_requirement_map(job_text).values(), key=lambda item: (-item.weight, item.concept))[:limit]
    cv_profile = _candidate_concept_strength(cv_text, cover_bonus=0.0)
    cover_profile = _candidate_concept_strength(cover_text, cover_bonus=-0.04)
    gaps: list[str] = []
    for signal in requirements:
        if cover_profile.get(signal.concept, 0.0) <= MATCH_DISPLAY_THRESHOLD:
            continue
        if cv_profile.get(signal.concept, 0.0) > MATCH_DISPLAY_THRESHOLD:
            continue
        label = _concept_label(signal.concept)
        if label not in gaps:
            gaps.append(label)
    return gaps


def _evidence_segments(text: str, concept: str, limit: int = 2) -> list[str]:
    segments = []
    for segment in _split_segments(text):
        concepts = _extract_concepts(segment)
        if concepts.get(concept, 0) > 0:
            segments.append(segment)
        if len(segments) >= limit:
            break
    return segments


def _requirement_status(cv_strength: float, cover_strength: float) -> str:
    if cv_strength >= 0.7:
        return "strong"
    if cv_strength > MATCH_DISPLAY_THRESHOLD or (cv_strength > 0 and cover_strength > MATCH_DISPLAY_THRESHOLD):
        return "weak"
    if cover_strength > MATCH_DISPLAY_THRESHOLD:
        return "cover_only"
    return "missing"


def _build_requirement_evidence(job_text: str, cv_text: str, cover_text: str, limit: int = 10) -> list[RequirementEvidence]:
    requirements = sorted(_build_requirement_map(job_text).values(), key=lambda item: (-item.weight, item.concept))
    cv_profile = _candidate_concept_strength(cv_text, cover_bonus=0.0)
    cover_profile = _candidate_concept_strength(cover_text, cover_bonus=-0.04)
    evidence: list[RequirementEvidence] = []

    for signal in requirements:
        if len(evidence) >= limit:
            break
        cv_strength = cv_profile.get(signal.concept, 0.0)
        cover_strength = cover_profile.get(signal.concept, 0.0)
        evidence.append(
            RequirementEvidence(
                requirement=_concept_label(signal.concept),
                priority=signal.priority,
                status=_requirement_status(cv_strength, cover_strength),
                cv_evidence=_evidence_segments(cv_text, signal.concept),
                cover_evidence=_evidence_segments(cover_text, signal.concept),
                target_line=signal.source_line,
            )
        )
    return evidence


def _detect_review_profile(job_text: str) -> str:
    families = _dominant_families(job_text)
    title = _split_segments(job_text)[0].lower() if _split_segments(job_text) else job_text.lower()
    if "aerospace" in title or "avionics" in title:
        return "Aerospace Engineering"
    if "automotive" in title:
        return "Automotive Engineering"
    if "manufacturing" in title or "production" in title:
        return "Manufacturing Engineering"
    if "mechanical" in title or "design engineer" in title or "cad" in title:
        return "Mechanical Engineering"
    if "software" in title or "backend" in title or "frontend" in title:
        return "Software Engineering"
    if "embedded" in title or "firmware" in title or "electrical" in title:
        return "Embedded / Electrical Engineering"
    if "data" in title or "analyst" in title:
        return "Data and Analytics"
    if "civil" in title or "structural" in title:
        return "Civil Engineering"
    if "software" in families:
        return "Software Engineering"
    if "mechanical" in families:
        return "Mechanical Engineering"
    if "electrical" in families:
        return "Embedded / Electrical Engineering"
    if "data" in families:
        return "Data and Analytics"
    return "General Engineering"


def _ats_section_check(cv_text: str) -> AtsCheck:
    headings = sum(
        1
        for line in cv_text.splitlines()
        if line.strip().lower() in {"education", "experience", "projects", "skills", "employment", "profile", "summary"}
    )
    if headings >= 2:
        return AtsCheck("Section recognition", "pass", "The CV has recognisable section headings for ATS parsing.")
    if headings == 1:
        return AtsCheck("Section recognition", "warn", "The CV has limited section headings. Add clearer labels like Education, Experience, Projects, and Skills.")
    return AtsCheck("Section recognition", "warn", "The CV does not expose clear section headings, which can make ATS parsing weaker.")


def _ats_date_check(cv_text: str) -> AtsCheck:
    has_dates = bool(
        re.search(
            r"(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{4}\b|\b20\d{2}\b|\b\d{4}\s*[-/]\s*(?:present|20\d{2})",
            cv_text,
        )
    )
    if has_dates:
        return AtsCheck("Date coverage", "pass", "The CV includes date patterns that ATS systems can usually map to experience timelines.")
    return AtsCheck("Date coverage", "warn", "The CV is missing clear date ranges. Add months or years to experience and education entries.")


def _ats_contact_check(cv_text: str) -> AtsCheck:
    has_email = bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", cv_text, re.I))
    has_phone = bool(re.search(r"(?:\+?\d[\d\s().-]{8,}\d)", cv_text))
    if has_email and has_phone:
        return AtsCheck("Contact parse", "pass", "The CV exposes email and phone information in ATS-friendly text.")
    if has_email or has_phone:
        return AtsCheck("Contact parse", "warn", "One core contact field is missing from the extracted text. Keep both email and phone in plain text.")
    return AtsCheck("Contact parse", "warn", "Contact details were not obvious in the extracted text.")


def _ats_noise_check(text: str) -> AtsCheck:
    weird_chars = len(re.findall(r"[�■□▪•◦¤]", text))
    if weird_chars == 0:
        return AtsCheck("Extraction noise", "pass", "The extracted text looks clean.")
    if weird_chars <= 3:
        return AtsCheck("Extraction noise", "warn", "A small amount of extraction noise was found. Check the uploaded formatting.")
    return AtsCheck("Extraction noise", "fail", "The uploaded document appears to contain extraction noise that could confuse ATS parsing.")


def _ats_bullet_check(cv_text: str) -> AtsCheck:
    segments = _split_segments(cv_text)
    if len(segments) >= 8:
        return AtsCheck("Content structure", "pass", "The CV has enough separable lines or bullets to scan cleanly.")
    if len(segments) >= 4:
        return AtsCheck("Content structure", "warn", "The CV is readable, but more clearly separated bullets would improve ATS and recruiter scanning.")
    return AtsCheck("Content structure", "warn", "The CV reads as a dense block. Break experience into more scan-friendly bullets.")


def _build_ats_diagnostics(cv_text: str, cover_text: str) -> AtsDiagnostics:
    checks = [
        _ats_section_check(cv_text),
        _ats_date_check(cv_text),
        _ats_contact_check(cv_text),
        _ats_noise_check(cv_text + "\n" + cover_text),
        _ats_bullet_check(cv_text),
    ]
    weights = {"pass": 20, "warn": 12, "fail": 5}
    score = int(round(sum(weights[item.status] for item in checks) / (len(checks) * 20) * 100))
    return AtsDiagnostics(score=max(20, min(score, 100)), checks=checks)


def _build_follow_up_questions(
    requirement_evidence: list[RequirementEvidence],
    ats_diagnostics: AtsDiagnostics,
) -> list[str]:
    questions: list[str] = []
    for item in requirement_evidence:
        if item.status == "missing":
            questions.append(f"Do you have any real example of {item.requirement} that is not yet in the CV or cover letter?")
        elif item.status == "cover_only":
            questions.append(f"Where in your CV can you prove {item.requirement}, rather than only claiming it in the cover letter?")
        if len(questions) >= 4:
            break
    for check in ats_diagnostics.checks:
        if check.status != "pass" and len(questions) < 6:
            questions.append(f"Can you strengthen this ATS area: {check.name.lower()}?")
    return questions[:6]


def _build_interview_questions(
    requirement_evidence: list[RequirementEvidence],
    keyword_overlap: list[str],
    missing_keywords: list[str],
) -> list[str]:
    questions: list[str] = []
    for item in requirement_evidence:
        if item.status in {"missing", "cover_only"}:
            questions.append(f"Tell me about a time you used {item.requirement}, and what result you achieved.")
        elif item.status == "strong":
            questions.append(f"Walk me through your strongest example of {item.requirement}. What did you own personally?")
        if len(questions) >= 4:
            break
    if len(questions) < 4 and keyword_overlap:
        questions.append(f"Which project best proves your {keyword_overlap[0]} experience?")
    if len(questions) < 4 and missing_keywords:
        questions.append(f"How would you close the gap on {missing_keywords[0]} if you started this role?")
    return questions[:4]


def _build_verdict(
    score: ReviewScore,
    requirement_evidence: list[RequirementEvidence],
    ats_diagnostics: AtsDiagnostics,
    fit_notes: list[str],
) -> ReviewVerdict:
    missing_count = sum(1 for item in requirement_evidence if item.status == "missing")
    cover_only_count = sum(1 for item in requirement_evidence if item.status == "cover_only")

    if score.total >= 78 and missing_count <= 2 and cover_only_count == 0:
        label = "Strong shortlist candidate"
    elif score.total >= 60 and missing_count <= 4:
        label = "Viable with stronger evidence"
    elif any("different disciplines" in note.lower() or "senior" in note.lower() for note in fit_notes):
        label = "Role mismatch"
    else:
        label = "Needs major retargeting"

    if ats_diagnostics.score >= 80 and cover_only_count == 0 and missing_count <= 2:
        confidence = "High confidence"
    elif ats_diagnostics.score >= 60 and missing_count <= 4:
        confidence = "Medium confidence"
    else:
        confidence = "Low confidence"

    rationale_parts = []
    if fit_notes:
        rationale_parts.append(fit_notes[0])
    if cover_only_count:
        rationale_parts.append("Several claims sit in the cover letter without equivalent CV evidence.")
    elif missing_count:
        rationale_parts.append("Some important requirements still lack clear evidence.")
    else:
        rationale_parts.append("The application evidence maps reasonably well to the advert.")

    return ReviewVerdict(label=label, confidence=confidence, rationale=" ".join(rationale_parts[:2]))


def _build_highlights(text: str, job_text: str, start_id: int, doc_name: str) -> list[Highlight]:
    highlights: list[Highlight] = []
    segments = _split_segments(text)
    focus = _high_priority_missing(job_text, text if doc_name == "CV" else "", text if doc_name != "CV" else "", limit=3)

    for segment in segments:
        if len(highlights) >= 3:
            break
        words = re.findall(r"\b\w+\b", segment)
        concepts = _extract_concepts(segment)
        lowered = segment.lower()

        if len(words) > 35:
            highlights.append(Highlight(start_id + len(highlights), segment, f"{doc_name} sentence is too dense.", "Rewrite this as two shorter points so a hiring manager can scan it quickly."))
            continue

        if concepts and any(verb in lowered for verb in IMPACT_VERBS) and not re.search(r"\b\d+(?:%|x|\+)?\b", segment):
            highlights.append(Highlight(start_id + len(highlights), segment, f"{doc_name} claim lacks proof.", "Add a measurable result, scale, or outcome so the point reads as credible evidence."))
            continue

        if doc_name == "Cover letter" and len(concepts) <= 1 and any(word in lowered for word in ("interested", "passion", "fit", "opportunity")):
            target = ", ".join(focus[:2]) if focus else "the role requirements"
            highlights.append(Highlight(start_id + len(highlights), segment, "Cover letter point is too generic.", f"Replace this with a role-specific sentence tied to {target} and one concrete example."))
            continue

        if doc_name == "CV" and len(words) >= 8 and not concepts and focus:
            highlights.append(Highlight(start_id + len(highlights), segment, "CV point does not help this application enough.", f"Use this space for evidence linked to {', '.join(focus[:2])} instead."))
            continue

        segment_labels = {_concept_label(concept) for concept in concepts}
        if focus and len(words) >= 8 and not any(item in segment_labels for item in focus):
            highlights.append(Highlight(start_id + len(highlights), segment, f"{doc_name} point is not aligned tightly enough to the advert.", f"Tie this point more directly to {', '.join(focus[:2])}."))
    return highlights


def _build_tailored_advice(
    job_text: str,
    cv_text: str,
    cover_text: str,
    cv_highlights: list[Highlight],
    cover_highlights: list[Highlight],
) -> list[TailoredAdvice]:
    focus = _high_priority_missing(job_text, cv_text, cover_text, limit=4)
    advice: list[TailoredAdvice] = []

    for highlight in cv_highlights[:2]:
        advice.append(
            TailoredAdvice(
                source="cv",
                reason=highlight.reason,
                excerpt=highlight.excerpt,
                suggestion=highlight.suggestion,
                target_requirements=focus[:2],
            )
        )
    for highlight in cover_highlights[:2]:
        advice.append(
            TailoredAdvice(
                source="cover_letter",
                reason=highlight.reason,
                excerpt=highlight.excerpt,
                suggestion=highlight.suggestion,
                target_requirements=focus[:2],
            )
        )

    if advice:
        return advice[:4]

    if focus:
        cv_segment = next((segment for segment in _split_segments(cv_text) if len(segment.split()) >= 6), "")
        if cv_segment:
            advice.append(
                TailoredAdvice(
                    source="cv",
                    reason="The CV needs clearer evidence for the target role.",
                    excerpt=cv_segment,
                    suggestion=f"Add explicit evidence for {', '.join(focus[:2])} with the tool used, what you owned, and the result.",
                    target_requirements=focus[:2],
                )
            )
        cover_segment = next((segment for segment in _split_segments(cover_text) if len(segment.split()) >= 6), "")
        if cover_segment:
            advice.append(
                TailoredAdvice(
                    source="cover_letter",
                    reason="The cover letter should connect your evidence to the advert more directly.",
                    excerpt=cover_segment,
                    suggestion=f"State how your projects or placements map to {', '.join(focus[:2])}, and give one concrete example.",
                    target_requirements=focus[:2],
                )
            )
    return advice[:4]

def recommend_roles(cv_text: str, jobs: list[dict[str, object]], limit: int = 5) -> list[RoleSuggestion]:
    evidence = _candidate_profile(cv_text, "")
    if not evidence:
        return []

    ranked: list[tuple[int, RoleSuggestion]] = []
    candidate_level = _detect_candidate_seniority(cv_text, "")
    for job in jobs:
        text = _job_text(job)
        requirements = _build_requirement_map(text)
        if not requirements:
            continue

        job_level = _detect_job_seniority(text)
        required_years = _extract_years_of_experience(text)
        early_career_role = _is_early_career_role(text)

        if candidate_level <= -1 and (job_level >= 2 or required_years >= 3):
            continue
        if candidate_level <= 0 and (job_level >= 3 or required_years >= 5):
            continue

        total_weight = sum(signal.weight for signal in requirements.values())
        matched_weight = sum(signal.weight * _coverage_strength(evidence.get(signal.concept, 0.0)) for signal in requirements.values())
        base_score = int(round(100 * matched_weight / max(total_weight, 0.01)))
        matched = [_concept_label(signal.concept) for signal in requirements.values() if evidence.get(signal.concept, 0.0) > MATCH_DISPLAY_THRESHOLD]
        if not matched:
            continue

        title_text = str(job.get("title") or "")
        title_keywords = _extract_keywords(title_text, limit=6)
        title_hits = sum(1 for token in title_keywords if token in _tokenize(cv_text))
        score = base_score + min(12, title_hits * 3)

        total_cap, _, _ = _fit_caps(text, cv_text, "")
        score = min(score, total_cap)
        if total_cap <= 35:
            score = min(score, 18)
        elif total_cap >= 80:
            score = max(score, 24)

        if candidate_level <= 0:
            if early_career_role:
                score += 12
            elif job_level >= 1:
                score = min(score - 8, 42)
        elif candidate_level == 1 and early_career_role:
            score += 6

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
    relevance, overlap, missing = _score_relevance(job_text, cv_text, cover_text, categories)
    tailoring = _score_tailoring(job_text, cv_text, cover_text)
    specificity = _score_specificity(cv_text, cover_text)
    structure = _score_structure(cv_text, cover_text)
    clarity = _score_clarity([cv_text, cover_text])
    profile = _detect_review_profile(job_text)
    total_cap, relevance_cap, fit_notes = _fit_caps(job_text, cv_text, cover_text)
    cover_only_gaps = _cover_only_requirement_gaps(job_text, cv_text, cover_text)

    if len(cover_only_gaps) >= 3:
        relevance = max(8, relevance - 12)
        total_cap = min(total_cap, 55)
        fit_notes.append(
            f"The cover letter names {', '.join(cover_only_gaps[:3])}, but the CV does not evidence them strongly enough yet."
        )
    elif len(cover_only_gaps) >= 2:
        relevance = max(8, relevance - 7)
        fit_notes.append(
            f"Some of the strongest claims sit in the cover letter rather than the CV: {', '.join(cover_only_gaps[:2])}."
        )

    relevance = min(relevance, relevance_cap)
    total = int(round(relevance * 0.4 + tailoring * 0.18 + specificity * 0.18 + structure * 0.12 + clarity * 0.12))
    total = min(total, total_cap)

    notes: list[str] = list(fit_notes)
    weak_categories = [category.label for category in categories if category.coverage < 55]
    if weak_categories:
        notes.append(f"Strengthen weak requirement areas: {', '.join(weak_categories[:3])}.")
    if tailoring < 68:
        notes.append("Make the cover letter more role-specific by naming the company, the role, and the most relevant requirements.")
    if specificity < 72:
        notes.append("Add stronger evidence: measurable outcomes, technical depth, and clear ownership.")
    if structure < 70:
        notes.append("Keep the CV concise and the cover letter tightly focused on the target role.")
    if clarity < 70:
        notes.append("Shorten dense sentences so the strongest evidence is easy to scan.")

    cv_highlights = _build_highlights(cv_text, job_text, 1, "CV")
    cover_highlights = _build_highlights(cover_text, job_text, 101, "Cover letter")
    tailored_advice = _build_tailored_advice(job_text, cv_text, cover_text, cv_highlights, cover_highlights)
    requirement_evidence = _build_requirement_evidence(job_text, cv_text, cover_text)
    ats_diagnostics = _build_ats_diagnostics(cv_text, cover_text)
    follow_up_questions = _build_follow_up_questions(requirement_evidence, ats_diagnostics)
    interview_questions = _build_interview_questions(requirement_evidence, overlap, missing)
    verdict = _build_verdict(
        ReviewScore(total=total, relevance=relevance, tailoring=tailoring, specificity=specificity, structure=structure, clarity=clarity),
        requirement_evidence,
        ats_diagnostics,
        fit_notes,
    )

    return ReviewResult(
        score=ReviewScore(total=total, relevance=relevance, tailoring=tailoring, specificity=specificity, structure=structure, clarity=clarity),
        profile=profile,
        verdict=verdict,
        notes=notes,
        keyword_overlap=overlap,
        missing_keywords=missing,
        cv_highlights=cv_highlights,
        cover_highlights=cover_highlights,
        tailored_advice=tailored_advice,
        requirement_evidence=requirement_evidence,
        ats_diagnostics=ats_diagnostics,
        follow_up_questions=follow_up_questions,
        interview_questions=interview_questions,
        categories=categories,
    )


def review_from_files(job_path: str, cv_path: str, cover_path: str) -> ReviewResult:
    return review(_read_text(job_path), _read_text(cv_path), _read_text(cover_path))


def to_json(result: ReviewResult) -> str:
    payload = {
        "score": result.score.__dict__,
        "profile": result.profile,
        "verdict": result.verdict.__dict__,
        "notes": result.notes,
        "keyword_overlap": result.keyword_overlap,
        "missing_keywords": result.missing_keywords,
        "cv_highlights": [highlight.__dict__ for highlight in result.cv_highlights],
        "cover_highlights": [highlight.__dict__ for highlight in result.cover_highlights],
        "tailored_advice": [advice.__dict__ for advice in result.tailored_advice],
        "requirement_evidence": [item.__dict__ for item in result.requirement_evidence],
        "ats_diagnostics": {
            "score": result.ats_diagnostics.score,
            "checks": [item.__dict__ for item in result.ats_diagnostics.checks],
        },
        "follow_up_questions": result.follow_up_questions,
        "interview_questions": result.interview_questions,
        "categories": [category.__dict__ for category in result.categories],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
