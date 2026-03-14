from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from getmeajob.providers.adzuna import (
    AdzunaClient,
    is_mechanical_engineering,
    is_year_in_industry,
    normalize_job,
)
from getmeajob.providers.company_feeds import fetch_company_jobs
from getmeajob.reviewer import review_from_files, to_json


def write_json(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def run_adzuna(args: argparse.Namespace) -> None:
    client = AdzunaClient(
        app_id=args.app_id,
        app_key=args.app_key,
        country=args.country,
        results_per_page=args.results_per_page,
        sleep_seconds=args.sleep_seconds,
    )

    raw_results = list(
        client.search(
            what=args.query,
            where=args.where,
            max_pages=args.max_pages,
        )
    )

    jobs = [normalize_job(item) for item in raw_results]

    jobs = [job for job in jobs if is_mechanical_engineering(job)]
    jobs = [job for job in jobs if is_year_in_industry(job)]

    rows = [job.__dict__ for job in jobs]

    if args.json_out:
        write_json(Path(args.json_out), rows)

    if args.csv_out:
        write_csv(Path(args.csv_out), rows)

    print(f"Fetched {len(rows)} matching roles (from {len(raw_results)} total).")


def run_company_jobs(args: argparse.Namespace) -> None:
    jobs = fetch_company_jobs()
    rows = [job.__dict__ | {"key_requirements": " | ".join(job.key_requirements)} for job in jobs]

    if args.json_out:
        write_json(Path(args.json_out), [job.__dict__ for job in jobs])

    if args.csv_out:
        write_csv(Path(args.csv_out), rows)

    print(f"Fetched {len(jobs)} UK engineering roles from official company feeds.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GetMeAJob job fetcher")
    sub = parser.add_subparsers(dest="provider", required=True)

    adzuna = sub.add_parser("adzuna", help="Fetch jobs via Adzuna API")
    adzuna.add_argument("--query", default="mechanical engineering year in industry")
    adzuna.add_argument("--where", default=None)
    adzuna.add_argument("--country", default="gb")
    adzuna.add_argument("--app-id", dest="app_id", default=None)
    adzuna.add_argument("--app-key", dest="app_key", default=None)
    adzuna.add_argument("--results-per-page", type=int, default=50)
    adzuna.add_argument("--max-pages", type=int, default=20)
    adzuna.add_argument("--sleep-seconds", type=float, default=1.0)
    adzuna.add_argument("--json-out", default="data/adzuna_mech_year_in_industry.json")
    adzuna.add_argument("--csv-out", default="data/adzuna_mech_year_in_industry.csv")

    company_jobs = sub.add_parser("company-jobs", help="Fetch UK engineering jobs from official company feeds")
    company_jobs.add_argument("--json-out", default="data/uk_engineering_company_jobs.json")
    company_jobs.add_argument("--csv-out", default="data/uk_engineering_company_jobs.csv")

    review = sub.add_parser("review", help="Review CV and cover letter against a job post")
    review.add_argument("--job", required=True, help="Path to job description text file")
    review.add_argument("--cv", required=True, help="Path to CV text file")
    review.add_argument("--cover-letter", required=True, help="Path to cover letter text file")
    review.add_argument("--out", default=None, help="Optional path to write JSON output")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.provider == "adzuna":
        run_adzuna(args)
    if args.provider == "company-jobs":
        run_company_jobs(args)
    if args.provider == "review":
        result = review_from_files(args.job, args.cv, args.cover_letter)
        payload = to_json(result)
        if args.out:
            Path(args.out).write_text(payload, encoding="utf-8")
        print(payload)


if __name__ == "__main__":
    main()
