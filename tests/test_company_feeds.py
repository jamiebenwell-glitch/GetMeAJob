from getmeajob.providers.company_feeds import (
    _clean_text,
    _extract_duration,
    _extract_lever_requirements,
    _extract_requirements,
    _extract_salary,
    _html_to_text,
    _is_target_job,
)


def test_is_target_job_filters_uk_engineering_roles() -> None:
    assert _is_target_job("Backend Engineer III", "London, UK")
    assert not _is_target_job("Talent Community - Engineering", "Cambridge, UK")
    assert not _is_target_job("Account Executive", "London, UK")


def test_extract_salary_and_duration() -> None:
    text = "London / UK Remote | Engineer III £78,000 - £110,000 | full-time permanent role"
    assert _extract_salary(text) == "£78,000 - £110,000"
    assert _extract_duration(text) == "full-time"


def test_extract_requirements_prefers_requirement_like_lines() -> None:
    text = """
    About the role
    We are looking for engineers with strong CAD and testing experience.
    You will build manufacturing tooling and work with production stakeholders.
    Benefits include pension and lunch.
    """
    requirements = _extract_requirements(text)
    assert requirements
    assert any("CAD" in item or "testing" in item for item in requirements)


def test_extract_lever_requirements_uses_structured_sections() -> None:
    requirements = _extract_lever_requirements(
        [
            {"text": "Perks and benefits", "content": "<li>Lunch</li>"},
            {
                "text": "Who might thrive here?",
                "content": "<li>Someone comfortable working across the full stack.</li><li>Strong React and .NET skills.</li>",
            },
        ]
    )
    assert requirements == [
        "Someone comfortable working across the full stack.",
        "Strong React and .NET skills.",
    ]


def test_clean_text_normalizes_currency_and_quotes() -> None:
    cleaned = _clean_text("Salary Â£95,000 â€™ remote Ł110,000")
    assert "£95,000" in cleaned
    assert "'" in cleaned
    assert "Ł" not in cleaned


def test_html_to_text_decodes_escaped_html() -> None:
    text = _html_to_text("&lt;p&gt;Backend Engineer&lt;/p&gt;&lt;li&gt;Strong Python skills&lt;/li&gt;")
    assert "Backend Engineer" in text
    assert "Strong Python skills" in text
