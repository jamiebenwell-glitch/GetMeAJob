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
    assert all(item.title != "Senior Software Engineer" for item in suggestions)


def test_recommend_roles_boosts_early_career_roles_for_student_cv() -> None:
    suggestions = recommend_roles(
        "Mechanical engineering undergraduate with CAD, testing, manufacturing, and prototype project work.",
        [
            {
                "title": "Mechanical Engineering Placement",
                "company": "Acme",
                "location": "Bristol, United Kingdom",
                "summary": "Placement role focused on CAD design, testing, and manufacturing support.",
                "key_requirements": ["CAD", "testing", "manufacturing", "analysis"],
                "apply_url": "https://example.com/placement",
            },
            {
                "title": "Mechanical Engineer",
                "company": "MidCo",
                "location": "Coventry, United Kingdom",
                "summary": "Mechanical engineering role focused on CAD, testing, and manufacturing support.",
                "key_requirements": ["CAD", "testing", "manufacturing"],
                "apply_url": "https://example.com/mid",
            },
        ],
    )

    assert suggestions
    assert suggestions[0].title == "Mechanical Engineering Placement"
    assert suggestions[0].score > suggestions[1].score


def test_recommend_roles_excludes_senior_mechanical_roles_for_undergrad_cv() -> None:
    suggestions = recommend_roles(
        "Mechanical engineering undergraduate with CAD, testing, manufacturing, and prototype project work.",
        [
            {
                "title": "Senior Mechanical Engineer",
                "company": "SeniorCo",
                "location": "Derby, United Kingdom",
                "summary": "Lead design reviews and own complex mechanical systems. Requires 5+ years of experience.",
                "key_requirements": ["CAD", "manufacturing", "analysis", "leadership"],
                "apply_url": "https://example.com/senior-mech",
            },
            {
                "title": "Mechanical Year in Industry",
                "company": "PlacementCo",
                "location": "Bristol, United Kingdom",
                "summary": "Year in industry role covering CAD, testing, and manufacturing support.",
                "key_requirements": ["CAD", "testing", "manufacturing"],
                "apply_url": "https://example.com/placement-mech",
            },
        ],
    )

    assert suggestions
    assert suggestions[0].title == "Mechanical Year in Industry"
    assert all(item.title != "Senior Mechanical Engineer" for item in suggestions)


def test_reviewer_gives_partial_credit_for_close_requirement_matches() -> None:
    result = review(
        "Backend Software Engineer. Build backend APIs and distributed systems on cloud infrastructure.",
        "Software engineering student who built backend services and REST APIs in Python. Deployed coursework to AWS.",
        "I want this backend role because I enjoy API design and scalable services.",
    )

    assert result.score.relevance >= 55
    assert "backend" in result.keyword_overlap
    assert "api" in result.keyword_overlap


def test_reviewer_does_not_overpenalize_missing_preferred_requirement() -> None:
    result = review(
        "Mechanical Design Engineer. Must have CAD, testing, manufacturing, and analysis experience. Preferred FEA experience.",
        "Mechanical engineering student with CAD, testing, manufacturing, and design project work. Improved prototype setup by 20%.",
        "I want this design role because it matches my CAD and manufacturing project experience.",
    )

    assert result.score.relevance >= 60
    assert result.score.total >= 60
    assert "cad" in result.keyword_overlap


def test_reviewer_ignores_demographic_questionnaire_text() -> None:
    result = review(
        (
            "Graduate Mechanical Engineer. Need CAD, manufacturing, testing, and analysis. "
            "To do this, we must ask applicants and employees if they have a disability or have ever had one."
        ),
        "Mechanical engineering student with CAD, testing, manufacturing, and analysis project work. Improved fixture setup time by 15%.",
        "I want this graduate role because it matches my CAD, testing, and manufacturing experience.",
    )

    blocked_terms = {"applicants", "employees", "disability", "ever"}
    combined_keywords = {item.lower() for item in result.keyword_overlap + result.missing_keywords}
    assert blocked_terms.isdisjoint(combined_keywords)
    assert all(
        not any(term in item.requirement.lower() or term in item.target_line.lower() for term in blocked_terms)
        for item in result.requirement_evidence
    )
    combined_guidance = " ".join(
        result.follow_up_questions
        + result.interview_questions
        + [item.suggestion for item in result.tailored_advice]
    ).lower()
    assert all(term not in combined_guidance for term in blocked_terms)
    assert result.score.relevance >= 60
