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


def test_reviewer_caps_student_application_for_senior_software_role() -> None:
    result = review(
        "Senior Software Engineer. Build backend APIs, cloud services, and distributed systems. Requires 5+ years of software engineering experience.",
        "Mechanical engineering undergraduate with CAD, testing, and manufacturing project experience. Completed a year in industry.",
        "I am an undergraduate student and I want to apply because I am interested in software and engineering.",
    )

    assert result.score.total <= 35
    assert result.score.relevance <= 30
    assert any("senior" in note.lower() or "early-career" in note.lower() for note in result.notes)
    assert any("5+" in note or "years of experience" in note.lower() for note in result.notes)


def test_recommend_roles_penalizes_senior_roles_for_student_cv() -> None:
    suggestions = recommend_roles(
        "Computer science undergraduate student with Python, APIs, and web app coursework.",
        [
            {
                "title": "Senior Software Engineer",
                "company": "BigCo",
                "location": "London, United Kingdom",
                "summary": "Own backend systems and mentor engineers. Requires 5+ years of software engineering experience.",
                "key_requirements": ["Python", "APIs", "cloud", "mentoring"],
                "apply_url": "https://example.com/senior",
            },
            {
                "title": "Graduate Software Engineer",
                "company": "GradCo",
                "location": "Manchester, United Kingdom",
                "summary": "Entry-level software engineering role focused on Python and APIs.",
                "key_requirements": ["Python", "APIs", "testing"],
                "apply_url": "https://example.com/graduate",
            },
        ],
    )

    assert suggestions
    assert suggestions[0].title == "Graduate Software Engineer"
    senior = next(item for item in suggestions if item.title == "Senior Software Engineer")
    graduate = next(item for item in suggestions if item.title == "Graduate Software Engineer")
    assert senior.score < graduate.score
