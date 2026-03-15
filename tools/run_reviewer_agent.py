from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from getmeajob.reviewer import review  # noqa: E402
from tests.reviewer_case_data import REVIEWER_CASES  # noqa: E402


def main() -> None:
    rows = []
    for case in REVIEWER_CASES:
        result = review(case["job"], case["cv"], case["cover"])
        rows.append(
            {
                "name": case["name"],
                "score": result.score.__dict__,
                "notes": result.notes,
                "keyword_overlap": result.keyword_overlap,
                "missing_keywords": result.missing_keywords,
                "tailored_advice": [item.__dict__ for item in result.tailored_advice],
            }
        )

    target = ROOT / "data" / "reviewer_benchmark_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(target)


if __name__ == "__main__":
    main()
