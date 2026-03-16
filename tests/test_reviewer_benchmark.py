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

    required_note = str(case.get("must_note") or "").strip().lower()
    if required_note:
        notes = " ".join(result.notes).lower()
        assert required_note in notes
