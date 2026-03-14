from getmeajob.reviewer import recommend_roles, review


def test_reviewer_filters_generic_keywords() -> None:
    result = review(
        "Mechanical engineering placement. Also allow flexible working. Need CAD, manufacturing, testing.",
        "Mechanical engineering student with CAD and testing work.",
        "I want this placement and have manufacturing project experience.",
    )

    assert "also" not in result.keyword_overlap
    assert "allow" not in result.missing_keywords
    assert "cad" in result.keyword_overlap


def test_reviewer_builds_document_highlights() -> None:
    result = review(
        "Mechanical engineering placement. Need CAD, manufacturing, testing, analysis.",
        "I designed a fixture for the student team and improved it.",
        "I am applying because I am interested in engineering and teamwork.",
    )

    assert result.cv_highlights
    assert result.cover_highlights


def test_reviewer_recommends_roles_from_cv() -> None:
    suggestions = recommend_roles(
        "Mechanical engineering student with CAD, testing, manufacturing, and analysis project work.",
        [
            {
                "title": "Mechanical Engineering Placement",
                "company": "Acme",
                "location": "Bristol, United Kingdom",
                "summary": "Placement role focused on CAD design, testing, and manufacturing support.",
                "key_requirements": ["CAD", "testing", "manufacturing", "analysis"],
                "apply_url": "https://example.com/acme",
            },
            {
                "title": "Marketing Graduate",
                "company": "OtherCo",
                "location": "London, United Kingdom",
                "summary": "Marketing, content, and social media planning role.",
                "key_requirements": ["marketing", "content"],
                "apply_url": "https://example.com/other",
            },
        ],
    )

    assert suggestions
    assert suggestions[0].company == "Acme"
    assert "cad" in suggestions[0].matched_keywords
