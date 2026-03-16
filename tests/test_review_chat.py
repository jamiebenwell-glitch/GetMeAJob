from getmeajob.review_chat import answer_review_question
from getmeajob.reviewer import review


def _application_payload() -> dict[str, object]:
    result = review(
        "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
        "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
        "I am interested in this role and believe I would be a strong fit for the company and the position.",
    )
    return {
        "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
        "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
        "cover_text": "I am interested in this role and believe I would be a strong fit for the company and the position.",
        "notes": result.notes,
        "missing_keywords": result.missing_keywords,
        "keyword_overlap": result.keyword_overlap,
        "categories": [item.__dict__ for item in result.categories],
        "tailored_advice": [item.__dict__ for item in result.tailored_advice],
        "requirement_evidence": [item.__dict__ for item in result.requirement_evidence],
        "follow_up_questions": result.follow_up_questions,
        "interview_questions": result.interview_questions,
        "role_suggestions": [],
    }


def test_review_chat_quotes_cover_letter_when_asked() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "What should I change in my cover letter?")

    assert "In your cover letter you wrote" in reply
    assert "company and the position" in reply


def test_review_chat_explains_experience_to_add() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "What experience should I add?")

    assert "Add explicit evidence" in reply or "expand" in reply
    assert any(keyword in reply.lower() for keyword in ("analysis", "manufacturing", "testing"))


def test_review_chat_explains_requirement_map() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "Show me the requirement map")

    assert "currently" in reply
    assert "CV evidence" in reply


def test_review_chat_returns_follow_up_questions() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "What else do you need from me?")

    assert "The next factual questions to answer are" in reply


def test_review_chat_returns_interview_handoff() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "What interview questions will they ask?")

    assert "Likely interview probes" in reply


def test_review_chat_uses_truth_preserving_rewrite_path() -> None:
    payload = _application_payload()
    reply = answer_review_question(payload, "Rewrite this CV bullet")

    assert "Keep the truth of" in reply
