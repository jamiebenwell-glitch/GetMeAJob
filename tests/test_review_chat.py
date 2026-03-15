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
