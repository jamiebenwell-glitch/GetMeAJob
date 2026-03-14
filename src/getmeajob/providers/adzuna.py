from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable

import requests

BASE_URL = "https://api.adzuna.com/v1/api/jobs"
DEFAULT_COUNTRY = "gb"
DEFAULT_RESULTS_PER_PAGE = 50
DEFAULT_SLEEP_SECONDS = 1.0

YEAR_IN_INDUSTRY_KEYWORDS = [
    "year in industry",
    "industrial placement",
    "placement year",
    "year-long",
    "12 month",
    "12-month",
    "sandwich year",
]


@dataclass(frozen=True)
class JobPosting:
    id: str
    title: str
    company: str | None
    location: str | None
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    created: str | None
    url: str | None
    description: str | None
    source: str


class AdzunaClient:
    def __init__(
        self,
        app_id: str | None = None,
        app_key: str | None = None,
        country: str = DEFAULT_COUNTRY,
        results_per_page: int = DEFAULT_RESULTS_PER_PAGE,
        sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    ) -> None:
        self.app_id = app_id or os.getenv("ADZUNA_APP_ID")
        self.app_key = app_key or os.getenv("ADZUNA_APP_KEY")
        self.country = country
        self.results_per_page = results_per_page
        self.sleep_seconds = sleep_seconds

        if not self.app_id or not self.app_key:
            raise ValueError("Missing ADZUNA_APP_ID or ADZUNA_APP_KEY")

    def search(
        self,
        what: str,
        where: str | None = None,
        max_pages: int = 50,
    ) -> Iterable[dict]:
        page = 1
        while page <= max_pages:
            url = f"{BASE_URL}/{self.country}/search/{page}"
            params = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "results_per_page": self.results_per_page,
                "what": what,
                "content-type": "application/json",
            }
            if where:
                params["where"] = where

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", [])

            if not results:
                break

            for item in results:
                yield item

            page += 1
            time.sleep(self.sleep_seconds)


def normalize_job(raw: dict) -> JobPosting:
    company = None
    if isinstance(raw.get("company"), dict):
        company = raw.get("company", {}).get("display_name")

    location = None
    if isinstance(raw.get("location"), dict):
        location = raw.get("location", {}).get("display_name")

    return JobPosting(
        id=str(raw.get("id")),
        title=raw.get("title") or "",
        company=company,
        location=location,
        salary_min=raw.get("salary_min"),
        salary_max=raw.get("salary_max"),
        currency=raw.get("salary_currency"),
        created=raw.get("created"),
        url=raw.get("redirect_url"),
        description=raw.get("description"),
        source="adzuna",
    )


def is_year_in_industry(job: JobPosting) -> bool:
    text = " ".join(
        part.lower()
        for part in [job.title or "", job.description or ""]
        if part
    )
    return any(keyword in text for keyword in YEAR_IN_INDUSTRY_KEYWORDS)


def is_mechanical_engineering(job: JobPosting) -> bool:
    text = " ".join(
        part.lower()
        for part in [job.title or "", job.description or ""]
        if part
    )
    return "mechanical" in text and "engineering" in text