from __future__ import annotations

from pathlib import Path
from typing import Any
import difflib
import json
import os

from authlib.integrations.starlette_client import OAuth
from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from getmeajob.ingest import extract_job_text_from_url, extract_text_from_bytes
from getmeajob.interview_prep import build_interview_prep
from getmeajob.review_chat import answer_review_question
from getmeajob.reviewer import recommend_roles, review
from getmeajob.storage import (
    create_review_run,
    get_draft,
    list_evidence_bank,
    get_review_run,
    get_revision,
    get_user,
    group_drafts,
    init_db,
    latest_draft_by_kind,
    list_drafts,
    list_revisions,
    list_review_history,
    review_outcome_summary,
    save_draft,
    update_review_outcome,
    upsert_user,
    upsert_evidence_item,
)


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR.parent.parent / "data"
JOBS_PATH = DATA_DIR / "uk_engineering_company_jobs.json"
GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"


app = FastAPI(title="GetMeAJob Reviewer")
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET", "dev-session-secret-change-me"),
    same_site="lax",
    https_only=os.getenv("SESSION_HTTPS_ONLY", "1") == "1",
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


def _public_base_url(request: Request) -> str:
    configured = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured

    forwarded_proto = request.headers.get("x-forwarded-proto", "").strip()
    forwarded_host = request.headers.get("x-forwarded-host", "").strip()
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def _auth_status(request: Request) -> dict[str, Any]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    session_secret = os.getenv("SESSION_SECRET", "").strip()
    auth_enabled = _auth_enabled()
    missing: list[str] = []
    if not client_id:
        missing.append("GOOGLE_CLIENT_ID")
    if not client_secret:
        missing.append("GOOGLE_CLIENT_SECRET")
    if not session_secret:
        missing.append("SESSION_SECRET")

    return {
        "enabled": auth_enabled,
        "configured": auth_enabled,
        "public_base_url": _public_base_url(request),
        "redirect_uri": f"{_public_base_url(request)}/auth/google/callback",
        "missing": missing,
        "https_only_cookie": os.getenv("SESSION_HTTPS_ONLY", "1") == "1",
    }


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
    auth_status = _auth_status(request)
    auth_enabled = bool(auth_status["enabled"])
    return {
        "user": user,
        "active_nav": active_nav,
        "auth_enabled": auth_enabled,
        "auth_status": auth_status,
        "auth_redirect_uri": str(auth_status["redirect_uri"]),
        "auth_requirements": list(auth_status["missing"]),
        "auth_error": str(request.session.pop("auth_error", "")),
        "auth_next": str(request.url.path or "/review"),
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
        "profile": "",
        "verdict": {},
        "notes": [],
        "keyword_overlap": [],
        "missing_keywords": [],
        "cv_highlights": [],
        "cover_highlights": [],
        "tailored_advice": [],
        "requirement_evidence": [],
        "ats_diagnostics": {"score": 0, "checks": []},
        "follow_up_questions": [],
        "interview_questions": [],
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


def _history_chart_points(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = list(reversed(history))
    return [
        {
            "label": item["created_at"],
            "score": int(item["score_total"]),
            "job_title": item["job_title"],
        }
        for item in ordered
    ]


def _save_application_evidence(user_id: int, review_id: int, application: dict[str, Any]) -> None:
    requirement_map = application.get("requirement_evidence") or []
    stored: set[str] = set()
    for item in requirement_map:
        if not isinstance(item, dict):
            continue
        requirement = str(item.get("requirement") or "").strip()
        cv_evidence = item.get("cv_evidence") or []
        if not isinstance(cv_evidence, list):
            continue
        for excerpt in cv_evidence[:2]:
            cleaned = str(excerpt or "").strip()
            if not cleaned or cleaned in stored:
                continue
            stored.add(cleaned)
            upsert_evidence_item(
                user_id,
                title=requirement or "Evidence from CV",
                excerpt=cleaned,
                tags=[requirement] if requirement else [],
                source_review_id=review_id,
            )


def _line_diff(previous: str, current: str) -> list[dict[str, str]]:
    previous_lines = previous.splitlines() or [previous]
    current_lines = current.splitlines() or [current]
    matcher = difflib.SequenceMatcher(a=previous_lines, b=current_lines)
    blocks: list[dict[str, str]] = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for line in current_lines[j1:j2]:
                if line.strip():
                    blocks.append({"kind": "same", "text": line})
        elif tag == "insert":
            for line in current_lines[j1:j2]:
                if line.strip():
                    blocks.append({"kind": "added", "text": line})
        elif tag == "delete":
            for line in previous_lines[i1:i2]:
                if line.strip():
                    blocks.append({"kind": "removed", "text": line})
        elif tag == "replace":
            for line in previous_lines[i1:i2]:
                if line.strip():
                    blocks.append({"kind": "removed", "text": line})
            for line in current_lines[j1:j2]:
                if line.strip():
                    blocks.append({"kind": "added", "text": line})

    return blocks[:80]


def _revision_payload(user_id: int, draft_id: int, revision_id: int | None = None) -> dict[str, Any]:
    draft = get_draft(user_id, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found.")

    revisions = list_revisions(user_id, draft_id)
    if not revisions:
        raise HTTPException(status_code=404, detail="No revisions found.")

    selected = revisions[-1]
    if revision_id is not None:
        selected = next((item for item in revisions if int(item["id"]) == revision_id), None) or selected

    selected_index = revisions.index(selected)
    previous = revisions[selected_index - 1] if selected_index > 0 else None
    previous_content = str(previous["content"]) if previous else ""
    selected_content = str(selected["content"])
    diff_blocks = _line_diff(previous_content, selected_content)

    summary = {
        "added": sum(1 for block in diff_blocks if block["kind"] == "added"),
        "removed": sum(1 for block in diff_blocks if block["kind"] == "removed"),
        "unchanged": sum(1 for block in diff_blocks if block["kind"] == "same"),
    }

    return {
        "draft": {
            "id": draft["id"],
            "kind": draft["kind"],
            "title": draft["title"],
        },
        "revisions": [
            {
                "id": item["id"],
                "created_at": item["created_at"],
                "preview": str(item["content"]).strip()[:140],
            }
            for item in reversed(revisions)
        ],
        "selected_revision": {
            "id": selected["id"],
            "created_at": selected["created_at"],
        },
        "previous_revision": (
            {
                "id": previous["id"],
                "created_at": previous["created_at"],
            }
            if previous
            else None
        ),
        "summary": summary,
        "diff_blocks": diff_blocks,
    }


def _review_page_context(
    request: Request,
    applications: list[dict[str, Any]],
    has_feedback: bool,
    page_warnings: list[str] | None = None,
) -> dict[str, Any]:
    user = _current_user(request)
    drafts_grouped = {"cv": [], "cover_letter": []}
    history: list[dict[str, Any]] = []
    evidence_bank: list[dict[str, Any]] = []
    outcome_summary = {"applied": 0, "interview": 0, "reject": 0, "offer": 0}
    warnings = list(page_warnings or [])
    if user:
        try:
            drafts_grouped = group_drafts(list_drafts(int(user["id"])))
        except Exception:
            warnings.append("Saved drafts could not be loaded right now.")
        try:
            history = list_review_history(int(user["id"]))
        except Exception:
            warnings.append("Review history could not be loaded right now.")
        try:
            evidence_bank = list_evidence_bank(int(user["id"]))
        except Exception:
            warnings.append("Evidence bank could not be loaded right now.")
        try:
            outcome_summary = review_outcome_summary(int(user["id"]))
        except Exception:
            warnings.append("Outcome stats could not be loaded right now.")

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
        "history_chart_points": _history_chart_points(history),
        "evidence_bank": evidence_bank,
        "outcome_summary": outcome_summary,
        "page_warnings": warnings,
    }
    return context


def _review_application_from_history(review_run: dict[str, Any]) -> dict[str, Any]:
    application = _empty_application(1)
    payload = review_run.get("application_payload")
    if isinstance(payload, dict):
        application.update(payload)
    else:
        application.update(
            {
                "job": str(review_run.get("job_title") or ""),
                "job_url": str(review_run.get("job_url") or ""),
                "cv_draft_title": str(review_run.get("cv_title") or "Saved CV"),
                "cover_draft_title": str(review_run.get("cover_title") or "Saved Cover Letter"),
                "score": {
                    "total": int(review_run.get("score_total") or 0),
                    "relevance": int(review_run.get("score_relevance") or 0),
                    "tailoring": int(review_run.get("score_tailoring") or 0),
                    "specificity": int(review_run.get("score_specificity") or 0),
                    "structure": int(review_run.get("score_structure") or 0),
                    "clarity": int(review_run.get("score_clarity") or 0),
                },
                "notes": [
                    "This saved review was created before full snapshot storage was enabled.",
                    "Scores are preserved, but the original CV and cover letter text were not stored in that older format.",
                ],
            }
        )
    application["index"] = 1
    application["errors"] = list(application.get("errors") or [])
    application["notes"] = list(application.get("notes") or [])
    application["keyword_overlap"] = list(application.get("keyword_overlap") or [])
    application["missing_keywords"] = list(application.get("missing_keywords") or [])
    application["profile"] = str(application.get("profile") or "")
    application["verdict"] = dict(application.get("verdict") or {})
    application["cv_highlights"] = list(application.get("cv_highlights") or [])
    application["cover_highlights"] = list(application.get("cover_highlights") or [])
    application["tailored_advice"] = list(application.get("tailored_advice") or [])
    application["requirement_evidence"] = list(application.get("requirement_evidence") or [])
    application["ats_diagnostics"] = dict(application.get("ats_diagnostics") or {"score": 0, "checks": []})
    application["follow_up_questions"] = list(application.get("follow_up_questions") or [])
    application["interview_questions"] = list(application.get("interview_questions") or [])
    application["categories"] = list(application.get("categories") or [])
    application["role_suggestions"] = list(application.get("role_suggestions") or [])
    application["cv_segments"] = list(application.get("cv_segments") or [])
    application["cover_segments"] = list(application.get("cover_segments") or [])
    return application


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


@app.get("/interview-prep", response_class=HTMLResponse)
def interview_prep_page(request: Request) -> HTMLResponse:
    context = {
        **_common_context(request, "interview-prep"),
    }
    return templates.TemplateResponse(request, "interview_prep.html", context)


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


@app.get("/review/history/{review_id}", response_class=HTMLResponse)
def review_history_page(request: Request, review_id: int) -> HTMLResponse:
    user = _current_user(request)
    if user is None:
        return RedirectResponse(url="/auth/login/google?next=/review", status_code=303)
    review_run = get_review_run(int(user["id"]), review_id)
    if review_run is None:
        raise HTTPException(status_code=404, detail="Saved review not found.")
    applications = [_review_application_from_history(review_run)]
    return templates.TemplateResponse(
        request,
        "review.html",
        _review_page_context(request, applications, True),
    )


@app.get("/healthz", response_class=JSONResponse)
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/auth/status", response_class=JSONResponse)
def auth_status(request: Request) -> JSONResponse:
    return JSONResponse(_auth_status(request))


@app.get("/auth/login/google")
async def auth_login_google(request: Request) -> RedirectResponse:
    if not _auth_enabled():
        raise HTTPException(status_code=503, detail="Google login is not configured.")
    next_path = str(request.query_params.get("next") or "/review")
    if not next_path.startswith("/"):
        next_path = "/review"
    request.session["auth_next"] = next_path
    redirect_uri = f"{_public_base_url(request)}/auth/google/callback"
    return await oauth.google.authorize_redirect(
        request,
        redirect_uri,
        prompt="select_account",
    )


@app.get("/auth/google/callback")
async def auth_google_callback(request: Request) -> RedirectResponse:
    if not _auth_enabled():
        raise HTTPException(status_code=503, detail="Google login is not configured.")
    next_path = str(request.session.pop("auth_next", "/review"))
    if not next_path.startswith("/"):
        next_path = "/review"

    try:
        token = await oauth.google.authorize_access_token(request)
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = await oauth.google.parse_id_token(request, token)
        if not userinfo:
            raise HTTPException(status_code=401, detail="Google login failed.")
    except Exception:
        request.session["auth_error"] = "Google sign-in did not complete. Try again or check the OAuth client setup."
        return RedirectResponse(url=next_path, status_code=303)

    user = upsert_user(
        google_sub=str(userinfo["sub"]),
        email=str(userinfo["email"]),
        name=str(userinfo.get("name") or userinfo["email"]),
        picture=str(userinfo.get("picture") or ""),
    )
    _login_user(request, user)
    return RedirectResponse(url=next_path, status_code=303)


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


@app.post("/api/review-assistant", response_class=JSONResponse)
async def review_assistant_endpoint(request: Request) -> JSONResponse:
    payload = await request.json()
    question = str(payload.get("question") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")
    application = payload.get("application")
    if not isinstance(application, dict):
        raise HTTPException(status_code=400, detail="Application payload is required.")
    answer = answer_review_question(application, question)
    return JSONResponse({"answer": answer})


@app.post("/api/interview-prep", response_class=JSONResponse)
async def interview_prep_endpoint(request: Request) -> JSONResponse:
    payload = await request.json()
    application = payload.get("application")
    if not isinstance(application, dict):
        raise HTTPException(status_code=400, detail="Application payload is required.")
    prep = build_interview_prep(application, _load_company_jobs(), live_research=not _is_test_mode())
    return JSONResponse(prep)


@app.post("/api/review-runs/{review_id}/outcome", response_class=JSONResponse)
async def review_outcome_endpoint(request: Request, review_id: int) -> JSONResponse:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    payload = await request.json()
    outcome_status = str(payload.get("outcome_status") or "").strip()
    updated = update_review_outcome(int(user["id"]), review_id, outcome_status)
    if updated is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return JSONResponse(updated)


@app.get("/api/drafts/{draft_id}/revisions", response_class=JSONResponse)
def draft_revisions_endpoint(request: Request, draft_id: int, revision_id: int | None = None) -> JSONResponse:
    user = _current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Sign in required.")
    payload = _revision_payload(int(user["id"]), draft_id, revision_id)
    return JSONResponse(payload)


@app.post("/review", response_class=HTMLResponse)
async def review_submit(request: Request) -> HTMLResponse:
    form = await request.form()
    user = _current_user(request)
    company_jobs = _load_company_jobs()
    page_warnings: list[str] = []

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
            try:
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
            except Exception:
                page_warnings.append("Your review ran, but the latest draft changes could not be saved.")

        result = review(job_text, cv_text, cover_text)
        application["score"] = result.score.__dict__
        application["profile"] = result.profile
        application["verdict"] = result.verdict.__dict__
        application["notes"] = result.notes
        application["keyword_overlap"] = result.keyword_overlap
        application["missing_keywords"] = result.missing_keywords
        application["cv_highlights"] = [highlight.__dict__ for highlight in result.cv_highlights]
        application["cover_highlights"] = [highlight.__dict__ for highlight in result.cover_highlights]
        application["tailored_advice"] = [advice.__dict__ for advice in result.tailored_advice]
        application["requirement_evidence"] = [item.__dict__ for item in result.requirement_evidence]
        application["ats_diagnostics"] = {
            "score": result.ats_diagnostics.score,
            "checks": [item.__dict__ for item in result.ats_diagnostics.checks],
        }
        application["follow_up_questions"] = result.follow_up_questions
        application["interview_questions"] = result.interview_questions
        application["cv_segments"] = _annotate_segments(cv_text, result.cv_highlights)
        application["cover_segments"] = _annotate_segments(cover_text, result.cover_highlights)
        application["categories"] = [category.__dict__ for category in result.categories]
        role_suggestions = recommend_roles(cv_text, company_jobs)
        if job_url.strip():
            role_suggestions = [suggestion for suggestion in role_suggestions if suggestion.apply_url != job_url.strip()]
        application["role_suggestions"] = [suggestion.__dict__ for suggestion in role_suggestions]

        if user:
            saved_application = {
                "index": 1,
                "job": job_text,
                "job_url": job_url,
                "cv_text": cv_text,
                "cover_text": cover_text,
                "cv_draft_id": application["cv_draft_id"],
                "cover_draft_id": application["cover_draft_id"],
                "cv_draft_title": application["cv_draft_title"],
                "cover_draft_title": application["cover_draft_title"],
                "cv_file_name": application["cv_file_name"],
                "cover_letter_file_name": application["cover_letter_file_name"],
                "errors": [],
                "score": application["score"],
                "profile": application["profile"],
                "verdict": application["verdict"],
                "notes": application["notes"],
                "keyword_overlap": application["keyword_overlap"],
                "missing_keywords": application["missing_keywords"],
                "cv_highlights": application["cv_highlights"],
                "cover_highlights": application["cover_highlights"],
                "tailored_advice": application["tailored_advice"],
                "requirement_evidence": application["requirement_evidence"],
                "ats_diagnostics": application["ats_diagnostics"],
                "follow_up_questions": application["follow_up_questions"],
                "interview_questions": application["interview_questions"],
                "cv_segments": application["cv_segments"],
                "cover_segments": application["cover_segments"],
                "categories": application["categories"],
                "role_suggestions": application["role_suggestions"],
            }
            try:
                saved_review = create_review_run(
                    int(user["id"]),
                    job_title=_job_title(job_text, job_url),
                    job_url=job_url,
                    score=result.score.__dict__,
                    cv_draft_id=int(saved_cv["id"]) if saved_cv else None,
                    cover_draft_id=int(saved_cover["id"]) if saved_cover else None,
                    cv_title=str(saved_cv["title"]) if saved_cv else cv_draft_title,
                    cover_title=str(saved_cover["title"]) if saved_cover else cover_draft_title,
                    application_payload=saved_application,
                )
                if saved_review and saved_review.get("id"):
                    _save_application_evidence(int(user["id"]), int(saved_review["id"]), application)
            except Exception:
                page_warnings.append("Your review ran, but it could not be written to account history.")

        applications.append(application)

    if not applications:
        latest = latest_draft_by_kind(int(user["id"])) if user else {}
        applications = [_empty_application(latest_drafts=latest)]

    return templates.TemplateResponse(
        request,
        "review.html",
        _review_page_context(request, applications, True, page_warnings=page_warnings),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "getmeajob.webapp:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8010")),
        reload=False,
    )
