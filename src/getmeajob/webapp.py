from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from fastapi import FastAPI, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile

from getmeajob.ingest import extract_job_text_from_url, extract_text_from_bytes
from getmeajob.reviewer import recommend_roles, review

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent.parent / "data"
JOBS_PATH = DATA_DIR / "uk_engineering_company_jobs.json"

app = FastAPI(title="GetMeAJob Reviewer")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _normalize_text_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if isinstance(value, (UploadFile, StarletteUploadFile)):
            continue
        normalized.append(str(value or ""))
    return normalized


def _normalize_file_list(values: list[Any]) -> list[UploadFile | None]:
    normalized: list[UploadFile | None] = []
    for value in values:
        if isinstance(value, (UploadFile, StarletteUploadFile)) and value.filename:
            normalized.append(value)
        else:
            normalized.append(None)
    return normalized


async def _read_upload(upload: UploadFile | None) -> str:
    if upload is None or not upload.filename:
        return ""
    content = await upload.read()
    if not content:
        return ""
    return extract_text_from_bytes(upload.filename, content)


def _empty_application(index: int = 1) -> dict[str, Any]:
    return {
        "index": index,
        "job": "",
        "job_url": "",
        "cv_cached_text": "",
        "cover_cached_text": "",
        "cv_cached_name": "",
        "cover_cached_name": "",
        "cv_file_name": "",
        "cover_letter_file_name": "",
        "errors": [],
        "score": None,
        "notes": [],
        "keyword_overlap": [],
        "missing_keywords": [],
        "cv_highlights": [],
        "cover_highlights": [],
        "cv_segments": [],
        "cover_segments": [],
        "categories": [],
        "role_suggestions": [],
    }


def _load_company_jobs() -> list[dict[str, Any]]:
    if not JOBS_PATH.exists():
        return []
    jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    return sorted(jobs, key=lambda job: (job.get("company") or "", job.get("title") or ""))


def _page_context(applications: list[dict[str, Any]], has_feedback: bool) -> dict[str, Any]:
    jobs = _load_company_jobs()
    companies = sorted({job.get("company") for job in jobs if job.get("company")})
    locations = sorted({job.get("location") for job in jobs if job.get("location")})
    durations = sorted({job.get("duration") for job in jobs if job.get("duration")})
    providers = sorted({job.get("source_provider") for job in jobs if job.get("source_provider")})
    scored_applications = [application for application in applications if application.get("score")]
    return {
        "applications": applications,
        "has_feedback": has_feedback,
        "has_scored_results": bool(scored_applications),
        "scored_applications": scored_applications,
        "initial_workspace_tab": "results" if scored_applications else "reviewer",
        "jobs": jobs,
        "job_count": len(jobs),
        "company_count": len(companies),
        "location_count": len(locations),
        "provider_count": len(providers),
        "job_companies": companies,
        "job_locations": locations,
        "job_durations": durations,
        "job_providers": providers,
    }


def _annotate_segments(text: str, highlights: list[Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    raw_segments = [segment.strip() for segment in text.splitlines() if segment.strip()]
    if not raw_segments:
        raw_segments = [segment.strip() for segment in text.split(". ") if segment.strip()]

    for segment in raw_segments:
        entry: dict[str, Any] = {"text": segment, "highlight": None}
        for highlight in highlights:
            if highlight.excerpt and highlight.excerpt in segment:
                entry["highlight"] = highlight.__dict__
                break
        segments.append(entry)
    return segments


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        _page_context([_empty_application()], False),
    )


@app.get("/healthz", response_class=JSONResponse)
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.post("/", response_class=HTMLResponse)
async def submit(request: Request) -> HTMLResponse:
    form = await request.form()
    company_jobs = _load_company_jobs()
    jobs = _normalize_text_list(form.getlist("job"))
    job_urls = _normalize_text_list(form.getlist("job_url"))
    cv_cached_texts = _normalize_text_list(form.getlist("cv_cached_text"))
    cover_cached_texts = _normalize_text_list(form.getlist("cover_cached_text"))
    cv_cached_names = _normalize_text_list(form.getlist("cv_cached_name"))
    cover_cached_names = _normalize_text_list(form.getlist("cover_cached_name"))
    cv_files = _normalize_file_list(form.getlist("cv_file"))
    cover_files = _normalize_file_list(form.getlist("cover_letter_file"))

    count = max(
        len(jobs),
        len(job_urls),
        len(cv_cached_texts),
        len(cover_cached_texts),
        len(cv_cached_names),
        len(cover_cached_names),
        len(cv_files),
        len(cover_files),
    )
    applications: list[dict[str, Any]] = []

    for idx in range(count):
        application = _empty_application(idx + 1)
        job_text = jobs[idx] if idx < len(jobs) else ""
        job_url = job_urls[idx] if idx < len(job_urls) else ""
        cv_text = cv_cached_texts[idx] if idx < len(cv_cached_texts) else ""
        cover_text = cover_cached_texts[idx] if idx < len(cover_cached_texts) else ""
        cv_cached_name = cv_cached_names[idx] if idx < len(cv_cached_names) else ""
        cover_cached_name = cover_cached_names[idx] if idx < len(cover_cached_names) else ""
        cv_file = cv_files[idx] if idx < len(cv_files) else None
        cover_file = cover_files[idx] if idx < len(cover_files) else None

        application["job"] = job_text
        application["job_url"] = job_url
        application["cv_cached_text"] = cv_text
        application["cover_cached_text"] = cover_text
        application["cv_cached_name"] = cv_cached_name
        application["cover_cached_name"] = cover_cached_name
        application["cv_file_name"] = cv_file.filename if cv_file and cv_file.filename else cv_cached_name
        application["cover_letter_file_name"] = (
            cover_file.filename if cover_file and cover_file.filename else cover_cached_name
        )

        errors: list[str] = []

        if job_url.strip() and not job_text.strip():
            try:
                job_text = extract_job_text_from_url(job_url.strip())
            except Exception as exc:
                errors.append(f"Could not read job URL: {exc}")

        try:
            uploaded_cv_text = await _read_upload(cv_file)
            if uploaded_cv_text.strip():
                cv_text = uploaded_cv_text
                application["cv_file_name"] = cv_file.filename or application["cv_file_name"]
        except Exception as exc:
            errors.append(f"Could not read CV file: {exc}")

        try:
            uploaded_cover_text = await _read_upload(cover_file)
            if uploaded_cover_text.strip():
                cover_text = uploaded_cover_text
                application["cover_letter_file_name"] = cover_file.filename or application["cover_letter_file_name"]
        except Exception as exc:
            errors.append(f"Could not read cover letter file: {exc}")

        application["cv_cached_text"] = cv_text
        application["cover_cached_text"] = cover_text
        application["cv_cached_name"] = application["cv_file_name"]
        application["cover_cached_name"] = application["cover_letter_file_name"]

        if not (job_text.strip() or job_url.strip()):
            errors.append("Add a job advert URL or paste the job description.")
        if not cv_text.strip():
            errors.append("Upload a CV file in .txt, .pdf, or .docx format.")
        if not cover_text.strip():
            errors.append("Upload a cover letter file in .txt, .pdf, or .docx format.")

        application["errors"] = errors

        if not (job_text.strip() and cv_text.strip() and cover_text.strip()):
            applications.append(application)
            continue

        result = review(job_text, cv_text, cover_text)
        application["score"] = result.score.__dict__
        application["notes"] = result.notes
        application["keyword_overlap"] = result.keyword_overlap
        application["missing_keywords"] = result.missing_keywords
        application["cv_highlights"] = [highlight.__dict__ for highlight in result.cv_highlights]
        application["cover_highlights"] = [highlight.__dict__ for highlight in result.cover_highlights]
        application["cv_segments"] = _annotate_segments(cv_text, result.cv_highlights)
        application["cover_segments"] = _annotate_segments(cover_text, result.cover_highlights)
        application["categories"] = [category.__dict__ for category in result.categories]
        role_suggestions = recommend_roles(cv_text, company_jobs)
        if job_url.strip():
            role_suggestions = [suggestion for suggestion in role_suggestions if suggestion.apply_url != job_url.strip()]
        application["role_suggestions"] = [suggestion.__dict__ for suggestion in role_suggestions]
        applications.append(application)

    if not applications:
        applications = [_empty_application()]

    return templates.TemplateResponse(
        request,
        "index.html",
        _page_context(applications, True),
    )


if __name__ == "__main__":
    import os
    import uvicorn

    uvicorn.run(
        "getmeajob.webapp:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8010")),
        reload=False,
    )
