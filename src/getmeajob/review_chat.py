from __future__ import annotations

from typing import Any


def _normalize_items(values: list[Any] | None) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _segments(text: str) -> list[str]:
    raw = [segment.strip() for segment in text.replace("\r", "\n").split("\n") if segment.strip()]
    if raw:
        return raw
    return [segment.strip() for segment in text.split(". ") if segment.strip()]


def _quote(text: str, limit: int = 180) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "..."


def _weak_categories(application: dict[str, Any]) -> list[dict[str, Any]]:
    categories = application.get("categories") or []
    if not isinstance(categories, list):
        return []
    weak = [item for item in categories if int(item.get("coverage") or 0) < 60]
    return sorted(weak, key=lambda item: int(item.get("coverage") or 0))


def _tailored_by_source(application: dict[str, Any], source: str) -> list[dict[str, Any]]:
    advice_items = application.get("tailored_advice") or []
    if not isinstance(advice_items, list):
        return []
    return [item for item in advice_items if str(item.get("source") or "") == source]


def _top_suggestion(application: dict[str, Any]) -> dict[str, Any] | None:
    suggestions = application.get("role_suggestions") or []
    if not isinstance(suggestions, list) or not suggestions:
        return None
    return suggestions[0]


def _requirement_map(application: dict[str, Any]) -> list[dict[str, Any]]:
    items = application.get("requirement_evidence") or []
    if not isinstance(items, list):
        return []
    return items


def _evidence_lines(text: str, terms: list[str], limit: int = 2) -> list[str]:
    lowered_terms = [term.lower() for term in terms if term]
    matches: list[str] = []
    for segment in _segments(text):
        lowered = segment.lower()
        if any(term in lowered for term in lowered_terms):
            matches.append(segment)
        if len(matches) >= limit:
            break
    return matches


def _fallback_cv_line(application: dict[str, Any]) -> str:
    lines = _segments(str(application.get("cv_text") or ""))
    for line in lines:
        if len(line.split()) >= 6:
            return line
    return lines[0] if lines else ""


def _fallback_cover_line(application: dict[str, Any]) -> str:
    lines = _segments(str(application.get("cover_text") or ""))
    for line in lines:
        if len(line.split()) >= 6:
            return line
    return lines[0] if lines else ""


def answer_review_question(application: dict[str, Any], question: str) -> str:
    lower = str(question or "").lower()
    weak_categories = _weak_categories(application)
    missing_keywords = _normalize_items(application.get("missing_keywords"))
    matched_keywords = _normalize_items(application.get("keyword_overlap"))
    notes = _normalize_items(application.get("notes"))
    cv_advice = _tailored_by_source(application, "cv")
    cover_advice = _tailored_by_source(application, "cover_letter")
    top_suggestion = _top_suggestion(application)
    requirement_evidence = _requirement_map(application)
    follow_up_questions = _normalize_items(application.get("follow_up_questions"))
    interview_questions = _normalize_items(application.get("interview_questions"))
    cv_text = str(application.get("cv_text") or "")
    cover_text = str(application.get("cover_text") or "")

    if any(word in lower for word in ("role", "job", "instead")):
        if top_suggestion:
            overlap = _normalize_items(top_suggestion.get("matched_keywords"))
            return (
                f"A better live target is {top_suggestion.get('title')} at {top_suggestion.get('company')}. "
                f"It fits this CV because it overlaps on {', '.join(overlap[:3]) or 'the strongest matched skills'}."
            )
        return "There is not enough grounded evidence in this CV yet to recommend a stronger alternative role."

    if any(word in lower for word in ("rewrite", "improve this", "better version")):
        advice = cv_advice[0] if "cv" in lower else cover_advice[0] if "cover" in lower else (cv_advice[0] if cv_advice else cover_advice[0] if cover_advice else None)
        if advice:
            source_text = _quote(advice.get("excerpt"))
            target_requirements = _normalize_items(advice.get("target_requirements"))
            target_text = f" Tie it explicitly to {', '.join(target_requirements[:2])}." if target_requirements else ""
            return (
                f'Keep the truth of "{source_text}", but rewrite it more directly: '
                f'{advice.get("suggestion")}{target_text}'
            )
        if follow_up_questions:
            return f"I cannot rewrite this credibly yet without inventing evidence. Start by answering: {follow_up_questions[0]}"
        return "I cannot rewrite this credibly yet without inventing evidence. Add one concrete example, tool, and outcome first."

    if any(word in lower for word in ("cover", "letter")):
        advice = cover_advice[0] if cover_advice else None
        if advice:
            return (
                f'In your cover letter you wrote "{_quote(advice.get("excerpt"))}". '
                f'{advice.get("suggestion")}'
            )
        fallback = _fallback_cover_line(application)
        if fallback:
            return (
                f'One cover letter line to tighten is "{_quote(fallback)}". '
                "Name the company, the role, and one concrete example that proves you meet the advert."
            )
        return "The cover letter needs clearer tailoring: name the role, match the advert, and back it with one concrete example."

    if any(word in lower for word in ("cv", "resume")):
        advice = cv_advice[0] if cv_advice else None
        if advice:
            return (
                f'In your CV you wrote "{_quote(advice.get("excerpt"))}". '
                f'{advice.get("suggestion")}'
            )
        fallback = _fallback_cv_line(application)
        if fallback:
            return (
                f'One CV line to strengthen is "{_quote(fallback)}". '
                "Add the tool, the task, and the measurable result so the evidence reads credibly."
            )
        return "The CV needs stronger evidence lines with tools used, ownership, and measurable outcomes."

    if any(word in lower for word in ("add", "experience", "evidence", "missing")):
        targets = missing_keywords[:3]
        if targets:
            cv_matches = _evidence_lines(cv_text, targets)
            if cv_matches:
                return (
                    f'Add clearer evidence for {", ".join(targets)}. '
                    f'For example, expand "{_quote(cv_matches[0])}" with the tool used, what you owned, and the outcome.'
                )
            return (
                f'Add explicit evidence for {", ".join(targets)}. '
                "If you have done this in coursework, projects, placements, or societies, state the task, method, and result directly."
            )
        return "The strongest next step is to add clearer, measurable evidence to the experience you already mention."

    if any(word in lower for word in ("requirement", "map", "evidence map")):
        weak = [item for item in requirement_evidence if str(item.get("status")) in {"missing", "cover_only", "weak"}]
        if weak:
            item = weak[0]
            return (
                f'{item.get("requirement")} is currently {item.get("status").replace("_", " ")}. '
                f'CV evidence: { _quote((item.get("cv_evidence") or ["none yet"])[0]) }. '
                f'Cover letter evidence: { _quote((item.get("cover_evidence") or ["none yet"])[0]) }.'
            )
        return "The strongest requirements are already covered with evidence in both the CV and the cover letter."

    if any(word in lower for word in ("score", "low", "why", "fit")):
        weak_labels = [f'{item.get("label")} ({item.get("coverage")}%)' for item in weak_categories[:3]]
        summary = weak_labels or ["tailoring and evidence depth"]
        return (
            f'The score is being pulled down most by {", ".join(summary)}. '
            f'{notes[0] if notes else "The current evidence does not map tightly enough to the advert."}'
        )

    if any(word in lower for word in ("keyword", "requirement", "requirements")):
        return (
            f'The strongest matched requirements are {", ".join(matched_keywords[:4]) or "not clear enough yet"}. '
            f'The biggest gaps are {", ".join(missing_keywords[:4]) or "small in this pass"}.'
        )

    if any(word in lower for word in ("interview", "question", "questions")):
        if interview_questions:
            return "Likely interview probes: " + " | ".join(interview_questions[:3])
        return "The interviewer is most likely to probe your missing requirements and ask for concrete examples with results."

    if any(word in lower for word in ("follow up", "follow-up", "what do you need from me", "what else")):
        if follow_up_questions:
            return "The next factual questions to answer are: " + " | ".join(follow_up_questions[:3])
        return "I already have enough evidence to comment without extra follow-up questions."

    if weak_categories:
        category = weak_categories[0]
        return (
            f'Start with {category.get("label", "the weakest category").lower()}. '
            f'You need stronger evidence for {", ".join(_normalize_items(category.get("missing_keywords"))[:3]) or "the missing requirements"}.'
        )
    if cv_advice:
        advice = cv_advice[0]
        return f'You wrote "{_quote(advice.get("excerpt"))}". {advice.get("suggestion")}'
    if cover_advice:
        advice = cover_advice[0]
        return f'You wrote "{_quote(advice.get("excerpt"))}". {advice.get("suggestion")}'
    return "Use the next improvements, the tailored advice cards, and the weakest requirement category to decide what to fix first."
