from __future__ import annotations

import os
import re
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient


TEST_DB_PATH = Path(tempfile.gettempdir()) / "getmeajob_test.db"
os.environ["GETMEAJOB_DB_PATH"] = str(TEST_DB_PATH)
os.environ["TESTING"] = "1"
os.environ["SESSION_HTTPS_ONLY"] = "0"

from getmeajob import storage  # noqa: E402
from getmeajob.webapp import app  # noqa: E402


@pytest.fixture(autouse=True)
def configure_test_db(tmp_path: Path) -> None:
    storage.DB_PATH = tmp_path / "app.db"
    app.state.testing = True
    yield


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def test_root_redirects_to_jobs(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/jobs"


def test_jobs_page_renders_separately_from_review(client: TestClient) -> None:
    response = client.get("/jobs")
    assert response.status_code == 200
    assert "UK engineering roles from company-run hiring pages." in response.text
    assert 'class="panel jobs-filter-panel"' in response.text
    assert "jobs-results-panel" in response.text
    assert "Open in reviewer" in response.text
    assert "Saved work" not in response.text


def test_interview_prep_page_renders_shell(client: TestClient) -> None:
    response = client.get("/interview-prep")
    assert response.status_code == 200
    assert "Turn the reviewed application into a company-specific interview plan." in response.text
    assert "Research Sources" in response.text
    assert "Questions to Expect" in response.text


def test_review_page_renders_guest_workspace(client: TestClient) -> None:
    response = client.get("/review")
    assert response.status_code == 200
    assert "Tailor the application, then judge it like a hiring manager." in response.text
    assert "CV review workspace" in response.text
    assert "Save CV draft" in response.text
    assert "Paste CV text" in response.text
    assert "Upload CV file" in response.text
    assert "Paste cover letter text" in response.text
    assert "Upload cover letter file" in response.text
    assert 'class="review-layout"' in response.text
    assert 'class="panel sidebar-panel account-panel"' in response.text
    assert "Google sign-in is ready in the app" in response.text
    assert "/auth/google/callback" in response.text
    assert "Score trend" in response.text
    assert "Reusable proof points" in response.text


def test_auth_status_reports_missing_google_config(client: TestClient) -> None:
    response = client.get("/auth/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is False
    assert "GOOGLE_CLIENT_ID" in payload["missing"]
    assert payload["redirect_uri"].endswith("/auth/google/callback")


def test_extract_upload_returns_text(client: TestClient) -> None:
    response = client.post(
        "/api/extract-upload",
        files={"file": ("cv.txt", b"Mechanical engineering student with CAD and testing work.", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["text"].startswith("Mechanical engineering student")


def test_review_assistant_endpoint_returns_grounded_answer(client: TestClient) -> None:
    response = client.post(
        "/api/review-assistant",
        json={
            "question": "What should I change in my cover letter?",
            "application": {
                "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
                "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
                "cover_text": "I am interested in this role and believe I would be a strong fit for the company and the position.",
                "notes": ["Make the cover letter more role-specific by naming the company, the role, and the most relevant requirements."],
                "missing_keywords": ["analysis"],
                "keyword_overlap": ["cad", "testing", "manufacturing"],
                "categories": [{"label": "Technical", "coverage": 52, "missing_keywords": ["analysis"]}],
                "tailored_advice": [
                    {
                        "source": "cover_letter",
                        "reason": "Cover letter point is too generic.",
                        "excerpt": "I am interested in this role and believe I would be a strong fit for the company and the position.",
                        "suggestion": "Replace this with a role-specific sentence tied to analysis and one concrete example.",
                        "target_requirements": ["analysis"],
                    }
                ],
                "role_suggestions": [],
            },
        },
    )

    assert response.status_code == 200
    assert "In your cover letter you wrote" in response.json()["answer"]


def test_interview_prep_endpoint_returns_grounded_payload(client: TestClient) -> None:
    response = client.post(
        "/api/interview-prep",
        json={
            "application": {
                "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
                "job_url": "",
                "profile": "Mechanical Engineering",
                "requirement_evidence": [
                    {
                        "requirement": "Analysis",
                        "status": "missing",
                        "target_line": "Need CAD, manufacturing, testing, and analysis.",
                        "cv_evidence": [],
                        "cover_evidence": [],
                    }
                ],
                "interview_questions": [
                    "Tell me about a time you used testing to improve a design decision."
                ],
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["company"] == "Acme"
    assert len(payload["process_stages"]) >= 3
    assert len(payload["question_groups"]) == 3
    assert len(payload["questions_to_ask"]) >= 2


def test_signed_in_user_can_save_drafts(client: TestClient) -> None:
    login = client.get("/test/login", follow_redirects=False)
    assert login.status_code == 303

    response = client.post(
        "/api/drafts/save",
        json={
            "kind": "cv",
            "title": "Main CV",
            "content": "Mechanical engineering student with CAD, testing, and manufacturing project experience.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "Main CV"

    page = client.get("/review")
    assert page.status_code == 200
    assert "Main CV" in page.text
    assert "Use draft" in page.text
    assert "Compare changes" in page.text


def test_existing_database_schema_is_migrated_for_login_and_review(tmp_path: Path) -> None:
    storage.DB_PATH = tmp_path / "legacy.db"
    with sqlite3.connect(storage.DB_PATH) as connection:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                google_sub TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE document_drafts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE document_revisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                draft_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE review_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                job_title TEXT NOT NULL,
                job_url TEXT NOT NULL DEFAULT '',
                score_total INTEGER NOT NULL,
                score_relevance INTEGER NOT NULL,
                score_tailoring INTEGER NOT NULL,
                score_specificity INTEGER NOT NULL,
                score_structure INTEGER NOT NULL,
                score_clarity INTEGER NOT NULL,
                cv_draft_id INTEGER,
                cover_draft_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

    app.state.testing = True
    with TestClient(app) as legacy_client:
        login = legacy_client.get("/test/login", follow_redirects=False)
        assert login.status_code == 303

        response = legacy_client.post(
            "/review",
            data={
                "job": "Mechanical Design Engineer. Must have CAD, testing, manufacturing, and analysis experience.",
                "job_url": "",
                "cv_text": "Mechanical engineering student with CAD, testing, manufacturing, and design project work.",
                "cover_text": "I want this design role because it matches my CAD and manufacturing project experience.",
                "cv_draft_title": "Main CV",
                "cover_draft_title": "Main Cover Letter",
                "cv_draft_id": "",
                "cover_draft_id": "",
            },
        )

        assert response.status_code == 200
        assert "Review complete." in response.text
        assert "Main CV against" in response.text


def test_signed_in_user_can_fetch_revision_diff(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)

    first = client.post(
        "/api/drafts/save",
        json={
            "kind": "cv",
            "title": "Main CV",
            "content": "Mechanical engineering student\nCAD project work",
        },
    ).json()

    client.post(
        "/api/drafts/save",
        json={
            "kind": "cv",
            "title": "Main CV",
            "content": "Mechanical engineering student\nCAD project work\nImproved setup time by 15%",
            "draft_id": first["id"],
        },
    )

    response = client.get(f"/api/drafts/{first['id']}/revisions")
    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["title"] == "Main CV"
    assert len(payload["revisions"]) == 2
    assert payload["summary"]["added"] >= 1
    assert any(block["kind"] == "added" for block in payload["diff_blocks"])


def test_google_login_route_preserves_next_path_when_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import getmeajob.webapp as webapp

    class FakeGoogle:
        async def authorize_redirect(self, request, redirect_uri, prompt=None):
            assert request.session["auth_next"] == "/jobs"
            assert redirect_uri.endswith("/auth/google/callback")
            assert prompt == "select_account"
            return RedirectResponse(url="/google-consent", status_code=302)

    monkeypatch.setattr(webapp.oauth, "google", FakeGoogle(), raising=False)
    response = client.get("/auth/login/google?next=/jobs", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/google-consent"


def test_google_callback_redirects_back_with_error_when_exchange_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import getmeajob.webapp as webapp

    class FakeGoogle:
        async def authorize_redirect(self, request, redirect_uri, prompt=None):
            return RedirectResponse(url="/google-consent", status_code=302)

        async def authorize_access_token(self, request):
            raise RuntimeError("boom")

    monkeypatch.setattr(webapp.oauth, "google", FakeGoogle(), raising=False)

    with client as session_client:
        session_client.get("/auth/login/google?next=/review", follow_redirects=False)
        response = session_client.get("/auth/google/callback", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/review"

        review_page = session_client.get("/review")
        assert "Google sign-in failed" in review_page.text


def test_review_submission_saves_history_for_signed_in_user(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)

    response = client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "cover_text": "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    assert response.status_code == 200
    assert "Review complete." in response.text
    assert "Scored applications" in response.text
    assert "Roles that fit this CV" in response.text
    assert "Main CV against" in response.text
    assert "Score trend" in response.text
    assert "Main Cover Letter" in response.text
    assert 'id="history-chart"' in response.text
    assert "Next improvements" in response.text
    assert "What to change in your wording" in response.text
    assert "Hiring Manager View" in response.text
    assert "Requirement to evidence" in response.text
    assert "Parser checks" in response.text
    assert "Questions before rewriting" in response.text
    assert "Questions you should be ready for" in response.text
    assert "You wrote" in response.text
    assert "Try adding" in response.text
    assert "CV markup" not in response.text
    assert 'class="issue-card"' not in response.text
    assert 'class="result-summary-strip"' in response.text
    assert 'class="result-overview-grid"' in response.text

    review_page = client.get("/review")
    assert review_page.status_code == 200
    assert "Mechanical engineering placement at Acme" in review_page.text
    assert "Open review" in review_page.text
    assert "Reusable proof points" in review_page.text


def test_review_outcome_endpoint_updates_status(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)

    client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "cover_text": "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    response = client.post("/api/review-runs/1/outcome", json={"outcome_status": "interview"})
    assert response.status_code == 200
    assert response.json()["outcome_status"] == "interview"

    review_page = client.get("/review")
    assert 'option value="interview" selected' in review_page.text


def test_signed_in_review_populates_evidence_bank(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)

    client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "cover_text": "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    review_page = client.get("/review")
    assert review_page.status_code == 200
    assert "Reusable proof points" in review_page.text
    assert "prototype testing" in review_page.text or "manufacturing project work" in review_page.text


def test_signed_in_user_can_reopen_saved_review(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)

    response = client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "cover_text": "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )
    assert response.status_code == 200

    history_page = client.get("/review/history/1")
    assert history_page.status_code == 200
    assert "Review complete." in history_page.text
    assert "Scored applications" in history_page.text
    assert "Mechanical engineering placement at Acme" in history_page.text
    assert "Main CV against" in history_page.text


def test_signed_in_user_can_open_legacy_saved_review_without_snapshot(client: TestClient) -> None:
    client.get("/test/login", follow_redirects=False)
    storage.init_db()
    with storage._connection() as connection:
        connection.execute(
            """
            INSERT INTO review_runs (
                user_id,
                job_title,
                job_url,
                score_total,
                score_relevance,
                score_tailoring,
                score_specificity,
                score_structure,
                score_clarity,
                cv_title,
                cover_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (1, "Legacy Mechanical Role", "", 71, 72, 70, 68, 75, 69, "Legacy CV", "Legacy Cover"),
        )

    history_page = client.get("/review/history/1")
    assert history_page.status_code == 200
    assert "Legacy Mechanical Role" in history_page.text
    assert "This saved review was created before full snapshot storage was enabled." in history_page.text
    assert "71%" in history_page.text


def test_init_db_does_not_leave_locked_database_file(tmp_path: Path) -> None:
    db_path = tmp_path / "lock-check.db"
    storage.DB_PATH = db_path
    storage.init_db()
    db_path.unlink()
    assert not db_path.exists()


def test_review_submission_still_returns_results_if_history_write_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import getmeajob.webapp as webapp

    client.get("/test/login", follow_redirects=False)

    def fail_create_review_run(*args, **kwargs):
        raise RuntimeError("history write failed")

    monkeypatch.setattr(webapp, "create_review_run", fail_create_review_run)

    response = client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "cover_text": "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    assert response.status_code == 200
    assert "Review complete." in response.text
    assert "Scored applications" in response.text
    assert "Your review ran, but it could not be written to account history." in response.text


def test_review_page_still_renders_if_draft_or_history_load_fails(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import getmeajob.webapp as webapp

    client.get("/test/login", follow_redirects=False)

    def fail_list_drafts(user_id: int):
        raise RuntimeError("draft load failed")

    def fail_list_review_history(user_id: int, limit: int = 20):
        raise RuntimeError("history load failed")

    monkeypatch.setattr(webapp, "list_drafts", fail_list_drafts)
    monkeypatch.setattr(webapp, "list_review_history", fail_list_review_history)

    response = client.get("/review")

    assert response.status_code == 200
    assert "CV review workspace" in response.text
    assert "Saved drafts could not be loaded right now." in response.text
    assert "Review history could not be loaded right now." in response.text


def test_review_submission_keeps_strong_fit_above_pass_threshold(client: TestClient) -> None:
    response = client.post(
        "/review",
        data={
            "job": "Mechanical Design Engineer. Must have CAD, testing, manufacturing, and analysis experience. Preferred FEA experience.",
            "job_url": "",
            "cv_text": "Mechanical engineering student with CAD, testing, manufacturing, and design project work. Improved prototype setup by 20%.",
            "cover_text": "I want this design role because it matches my CAD and manufacturing project experience.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    assert response.status_code == 200
    match = re.search(r'<div class="score">(\d+)%</div>', response.text)
    assert match is not None
    assert int(match.group(1)) >= 60


def test_review_submission_keeps_senior_mismatch_low(client: TestClient) -> None:
    response = client.post(
        "/review",
        data={
            "job": "Senior Software Engineer. Build backend APIs, cloud services, and distributed systems. Requires 5+ years of software engineering experience.",
            "job_url": "",
            "cv_text": "Mechanical engineering undergraduate with CAD, testing, and manufacturing project experience. Completed a year in industry.",
            "cover_text": "I am an undergraduate student and I want to apply because I am interested in software and engineering.",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    assert response.status_code == 200
    match = re.search(r'<div class="score">(\d+)%</div>', response.text)
    assert match is not None
    assert int(match.group(1)) <= 35


def test_review_submission_shows_validation_feedback(client: TestClient) -> None:
    response = client.post(
        "/review",
        data={
            "job": "Mechanical engineering placement focused on CAD and manufacturing.",
            "job_url": "",
            "cv_text": "",
            "cover_text": "",
            "cv_draft_title": "Main CV",
            "cover_draft_title": "Main Cover Letter",
            "cv_draft_id": "",
            "cover_draft_id": "",
        },
    )

    assert response.status_code == 200
    assert "Needs input" in response.text
    assert "Upload a CV file in .txt, .pdf, or .docx format, or use a saved draft." in response.text
    assert "Upload a cover letter file in .txt, .pdf, or .docx format, or use a saved draft." in response.text

