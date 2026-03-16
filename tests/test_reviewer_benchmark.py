import pytest

from getmeajob.reviewer import review
from tests.reviewer_case_data import REVIEWER_CASES


def test_reviewer_benchmark_has_milestone_depth() -> None:
    assert len(REVIEWER_CASES) >= 100


@pytest.mark.parametrize("case", REVIEWER_CASES, ids=[case["name"] for case in REVIEWER_CASES])
def test_reviewer_benchmark_cases(case: dict[str, object]) -> None:
    result = review(str(case["job"]), str(case["cv"]), str(case["cover"]))

    assert int(case["score_min"]) <= result.score.total <= int(case["score_max"])

    for keyword in case.get("must_include", []):
        lowered = str(keyword).lower()
        assert lowered in [item.lower() for item in result.keyword_overlap]

    requirement_names = [item.requirement.lower() for item in result.requirement_evidence]
    for forbidden in case.get("must_exclude_requirements", []):
        assert str(forbidden).lower() not in requirement_names

    required_note = str(case.get("must_note") or "").strip().lower()
    if required_note:
        notes = " ".join(result.notes).lower()
        assert required_note in notes

    blocked_text = " ".join(
        result.keyword_overlap
        + result.missing_keywords
        + result.notes
        + result.follow_up_questions
        + result.interview_questions
        + [item.requirement for item in result.requirement_evidence]
        + [item.target_line for item in result.requirement_evidence]
        + [item.reason for item in result.tailored_advice]
        + [item.suggestion for item in result.tailored_advice]
    ).lower()
    for forbidden in case.get("must_exclude", []):
        assert str(forbidden).lower() not in blocked_text
