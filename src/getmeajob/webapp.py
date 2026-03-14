from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import os

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.middleware.sessions import SessionMiddleware

from getmeajob.ingest import extract_job_text_from_url, extract_text_from_bytes
from getmeajob.reviewer import recommend_roles, review
from getmeajob.storage import (
    create_review_run,
    get_user,
    group_drafts,
    init_db,
    latest_draft_by_kind,
    list_drafts,
    list_review_history,
    save_draft,
    upsert_user,
)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent.parent / "data"
JOBS_PATH = DATA_DIR / "uk_engineering_company_jobs.json"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


app = FastAPI(title="GetMeAJob Reviewer")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-session-secret-change-me"),
    same_site="lax",
    https_only=os.getenv("SESSION_HTTPS_ONLY", "0") == "1",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
oauth = OAuth()


def _register_oauth() -> None:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return
    oauth.register(
        name="google",
        server_metadata_url=GOOGLE_DISCOVERY_URL,
        client_id=client_id,
        client_secret=client_secret,
        client_kwargs={"scope": "openid email profile"},
    )


_register_oauth()


@app.on_event("startup")
def _startup() -> None:
    init_db()


def _auth_enabled() -> bool:
    return hasattr(oauth, "google")


def _current_user(request: Request) -> dict[str, Any] | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return get_user(int(user_id))


def _login_user(request: Request, user: dict[str, Any]) -> None:
    request.session["user_id"] = int(user["id"])
    request.session["user_name"] = str(user["name"])
    request.session["user_email"] = str(user["email"])
    request.session["user_picture"] = str(user.get("picture") or "")


def _is_test_mode() -> bool:
    return bool(getattr(app.state, "testing", False) or os.getenv("TESTING") == "1")


def _load_company_jobs() -> list[dict[str, Any]]:
    if not JOBS_PATH.exists():
        return []
    jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))
    return sorted(jobs, key=lambda job: (job.get("company") or "", job.get("title") or ""))


def _job_catalog_context() -> dict[str, Any]:
    jobs = _load_company_jobs()
    companies = sorted({job.get("company") for job in jobs if job.get("company")})
    locations = sorted({job.get("location") for job in jobs if job.get("location")})
    durations = sorted({job.get("duration") for job in jobs if job.get("duration")})
    providers = sorted({job.get("source_provider") for job in jobs if job.get("source_provider")})
    return {
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


def _common_context(request: Request, active_nav: str) -> dict[str, Any]:
    user = _current_user(request)
    return {
        "user": user,
        "active_nav": active_nav,
        "auth_enabled": _auth_enabled(),
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


def _empty_application(index: int = 1, latest_drafts: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    latest_drafts = latest_drafts or {}
    cv_draft = latest_drafts.get("cv")
    cover_draft = latest_drafts.get("cover_letter")
    return {
        "index": index,
        "job": "",
        "job_url": "",
        "cv_text": cv_draft["content"] if cv_draft else "",
        "cover_text": cover_draft["content"] if cover_draft else "",
        "cv_draft_id": cv_draft["id"] if cv_draft else "",
        "cover_draft_id": cover_draft["id"] if cover_draft else "",
        "cv_draft_title": cv_draft["title"] if cv_draft else "Main CV",
        "cover_draft_title": cover_draft["title"] if cover_draft else "Main Cover Letter",
        "cv_file_name": cv_draft["title"] if cv_draft else "",
        "cover_letter_file_name": cover_draft["title"] if cover_draft else "",
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


def _job_title(job_text: str, job_url: str) -> str:
    first_line = next((line.strip() for line in job_text.splitlines() if line.strip()), "")
    return first_line or job_url or "Untitled role"


def _review_page_context(
    request: Request,
    applications: list[dict[str, Any]],
    has_feedback: bool,
) -> dict[str, Any]:
    user = _current_user(request)
    drafts_grouped = {"cv": [], "cover_letter": []}
    history: list[dict[str, Any]] = []
    if user:
        drafts_grouped = group_drafts(list_drafts(int(user["id"])))
        history = list_review_history(int(user["id"]))

    scored_applications = [application for application in applications if application.get("score")]
    context = {
        **_common_context(request, "review"),
        "applications": applications,
        "has_feedback": has_feedback,
        "has_scored_results": bool(scored_applications),
        "scored_applications": scored_applications,
        "initial_workspace_tab": "results" if scored_applications else "reviewer",
        "drafts": drafts_grouped,
        "review_history": history,
    }
    return context


@app.get("/", response_class=HTMLResponse)
def index() -> RedirectResponse:
    return RedirectResponse(url="/jobs", status_code=303)


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(request: Request) -> HTMLResponse:
    context = {
        **_common_context(request, "jobs"),
        **_job_catalog_context(),
    }
    return templates.TemplateResponse(request, "jobs.html", context)


@app.get("/review", response_class=HTMLResponse)
def review_page(request: Request) -> HTMLResponse:
    user = _current_user(request)
    latest = latest_draft_by_kind(int(user["id"])) if user else {}
    applications = [_empty_application(latest_drafts=latest)]
    return templates.TemplateResponse(
        request,
        "review.html",
        _review_page_context(request, applications, False),
    )


@app.get("/healthz", response_class=JSONResponse)
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/auth/login/google")
async def auth_login_google(request: Request) -> RedirectResponse:
    if not _auth_enabled():
        raise HTTPException(status_code=503, detail="Google login is not configured.")
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request) -> RedirectResponse:
    if not _auth_enabled():
        raise HTTPException(status_code=503, detail="Google login is not configured.")
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = await oauth.google.parse_id_token(request, token)
    if not userinfo:
        raise HTTPException(status_code=401, detail="Google login failed.")

    user = upsert_user(
        google_sub=str(userinfo["sub"]),
        email=str(userinfo["email"]),
        name=str(userinfo.get("name") or userinfo["email"]),
        picture=str(userinfo.get("picture") or ""),
    )
    _login_user(request, user)
    return RedirectResponse(url="/review", status_code=303)


@app.get("/auth/logout")
def auth_logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/jobs", status_code=303)


@app.get("/test/login")
def test_login(request: Request, email: str = "test@example.com", name: str = "Test User", next: str = "/review") -> RedirectResponse:
    if not _is_test_mode():
        raise HTTPException(status_code=404)
    user = upsert_user(google_sub=f"test-{email}", email=email, name=name, picture="")
    _login_user(request, user)
    return RedirectResponse(url=next, status_code=303)


@app.post("/api/extract-upload", response_class=JSONResponse)
async def extract_upload(file: UploadFile) -> JSONResponse:
    text = await _read_upload(file)
    return JSONResponse({"filename": file.filename or "", "text": text})


@app.post("/api/drafts/save", response_class=JSONResponse)
async def save_draft_endpoint(request: Request) -> JSONResponse:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")

    payload = await request.json()
    kind = str(payload.get("kind") or "").strip()
    if kind not in {"cv", "cover_letter"}:
        raise HTTPException(status_code=400, detail="Invalid draft type.")

    title = str(payload.get("title") or "").strip()
    content = str(payload.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="Draft content cannot be empty.")

    draft_id = payload.get("draft_id")
    saved = save_draft(
        int(user["id"]),
        kind=kind,
        title=title,
        content=content,
        draft_id=int(draft_id) if draft_id else None,
    )
    return JSONResponse(saved)


@app.post("/review", response_class=HTMLResponse)
async def review_submit(request: Request) -> HTMLResponse:
    form = await request.form()
    user = _current_user(request)
    company_jobs = _load_company_jobs()

    jobs = _normalize_text_list(form.getlist("job"))
    job_urls = _normalize_text_list(form.getlist("job_url"))
    cv_texts = _normalize_text_list(form.getlist("cv_text"))
    cover_texts = _normalize_text_list(form.getlist("cover_text"))
    cv_draft_ids = _normalize_text_list(form.getlist("cv_draft_id"))
    cover_draft_ids = _normalize_text_list(form.getlist("cover_draft_id"))
    cv_draft_titles = _normalize_text_list(form.getlist("cv_draft_title"))
    cover_draft_titles = _normalize_text_list(form.getlist("cover_draft_title"))
    cv_files = _normalize_file_list(form.getlist("cv_file"))
    cover_files = _normalize_file_list(form.getlist("cover_letter_file"))

    count = max(
        len(jobs),
        len(job_urls),
        len(cv_texts),
        len(cover_texts),
        len(cv_draft_ids),
        len(cover_draft_ids),
        len(cv_draft_titles),
        len(cover_draft_titles),
        len(cv_files),
        len(cover_files),
    )
    applications: list[dict[str, Any]] = []

    for idx in range(count):
        application = _empty_application(idx + 1)
        job_text = jobs[idx] if idx < len(jobs) else ""
        job_url = job_urls[idx] if idx < len(job_urls) else ""
        cv_text = cv_texts[idx] if idx < len(cv_texts) else ""
        cover_text = cover_texts[idx] if idx < len(cover_texts) else ""
        cv_draft_id = cv_draft_ids[idx] if idx < len(cv_draft_ids) else ""
        cover_draft_id = cover_draft_ids[idx] if idx < len(cover_draft_ids) else ""
        cv_draft_title = cv_draft_titles[idx] if idx < len(cv_draft_titles) else "Main CV"
        cover_draft_title = cover_draft_titles[idx] if idx < len(cover_draft_titles) else "Main Cover Letter"
        cv_file = cv_files[idx] if idx < len(cv_files) else None
        cover_file = cover_files[idx] if idx < len(cover_files) else None

        application["job"] = job_text
        application["job_url"] = job_url
        application["cv_text"] = cv_text
        application["cover_text"] = cover_text
        application["cv_draft_id"] = cv_draft_id
        application["cover_draft_id"] = cover_draft_id
        application["cv_draft_title"] = cv_draft_title
        application["cover_draft_title"] = cover_draft_title
        application["cv_file_name"] = cv_file.filename if cv_file and cv_file.filename else cv_draft_title
        application["cover_letter_file_name"] = (
            cover_file.filename if cover_file and cover_file.filename else cover_draft_title
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

        application["cv_text"] = cv_text
        application["cover_text"] = cover_text

        if not (job_text.strip() or job_url.strip()):
            errors.append("Add a job advert URL or paste the job description.")
        if not cv_text.strip():
            errors.append("Upload a CV file in .txt, .pdf, or .docx format, or use a saved draft.")
        if not cover_text.strip():
            errors.append("Upload a cover letter file in .txt, .pdf, or .docx format, or use a saved draft.")

        application["errors"] = errors

        if not (job_text.strip() and cv_text.strip() and cover_text.strip()):
            applications.append(application)
            continue

        saved_cv: dict[str, Any] | None = None
        saved_cover: dict[str, Any] | None = None
        if user:
            saved_cv = save_draft(
                int(user["id"]),
                kind="cv",
                title=cv_draft_title,
                content=cv_text,
                draft_id=int(cv_draft_id) if cv_draft_id else None,
            )
            saved_cover = save_draft(
                int(user["id"]),
                kind="cover_letter",
                title=cover_draft_title,
                content=cover_text,
                draft_id=int(cover_draft_id) if cover_draft_id else None,
            )
            application["cv_draft_id"] = saved_cv["id"]
            application["cover_draft_id"] = saved_cover["id"]
            application["cv_draft_title"] = saved_cv["title"]
            application["cover_draft_title"] = saved_cover["title"]

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

        if user:
            create_review_run(
                int(user["id"]),
                job_title=_job_title(job_text, job_url),
                job_url=job_url,
                score=result.score.__dict__,
                cv_draft_id=int(saved_cv["id"]) if saved_cv else None,
                cover_draft_id=int(saved_cover["id"]) if saved_cover else None,
                cv_title=str(saved_cv["title"]) if saved_cv else cv_draft_title,
                cover_title=str(saved_cover["title"]) if saved_cover else cover_draft_title,
            )

        applications.append(application)

    if not applications:
        latest = latest_draft_by_kind(int(user["id"])) if user else {}
        applications = [_empty_application(latest_drafts=latest)]

    return templates.TemplateResponse(
        request,
        "review.html",
        _review_page_context(request, applications, True),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "getmeajob.webapp:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8010")),
        reload=False,
    )
