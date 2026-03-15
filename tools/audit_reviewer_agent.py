from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.reviewer_case_data import REVIEWER_CASES  # noqa: E402


def main() -> int:
    report_path = ROOT / "data" / "reviewer_benchmark_report.json"
    if not report_path.exists():
        print("Missing reviewer benchmark report.")
        return 1

    rows = json.loads(report_path.read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}

    failures: list[str] = []
    for case in REVIEWER_CASES:
        row = by_name.get(case["name"])
        if row is None:
            failures.append(f"{case['name']}: missing benchmark result")
            continue

        score = int(row["score"]["total"])
        if score < int(case["score_min"]) or score > int(case["score_max"]):
            failures.append(
                f"{case['name']}: score {score} outside expected band {case['score_min']}-{case['score_max']}"
            )

        for keyword in case.get("must_include", []):
            overlap = [item.lower() for item in row.get("keyword_overlap", [])]
            if str(keyword).lower() not in overlap:
                failures.append(f"{case['name']}: missing expected overlap '{keyword}'")

        must_note = str(case.get("must_note") or "").strip().lower()
        if must_note:
            notes = " ".join(row.get("notes", [])).lower()
            if must_note not in notes:
                failures.append(f"{case['name']}: missing expected note fragment '{must_note}'")

        if "undergrad" in case["name"] or "student" in case["name"]:
            if score > 50 and "senior" in str(case["job"]).lower():
                failures.append(f"{case['name']}: early-career candidate scored too highly for senior role")

    audit = {
        "total_cases": len(REVIEWER_CASES),
        "failures": failures,
        "passed": len(failures) == 0,
    }
    target = ROOT / "data" / "reviewer_benchmark_audit.json"
    target.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(target)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
