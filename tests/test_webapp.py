from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TEST_DB_PATH = Path(tempfile.gettempdir()) / "getmeajob_test.db"
os.environ["GETMEAJOB_DB_PATH"] = str(TEST_DB_PATH)
os.environ["TESTING"] = "1"

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
    assert "Company-hosted UK engineering jobs" in response.text
    assert "Open in reviewer" in response.text
    assert "Saved work" not in response.text


def test_review_page_renders_guest_workspace(client: TestClient) -> None:
    response = client.get("/review")
    assert response.status_code == 200
    assert "CV review workspace" in response.text
    assert "Save CV draft" in response.text
    assert "Sign in with Google to save drafts" in response.text
    assert "Score trend" in response.text


def test_extract_upload_returns_text(client: TestClient) -> None:
    response = client.post(
        "/api/extract-upload",
        files={"file": ("cv.txt", b"Mechanical engineering student with CAD and testing work.", "text/plain")},
    )
    assert response.status_code == 200
    assert response.json()["text"].startswith("Mechanical engineering student")


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

    review_page = client.get("/review")
    assert review_page.status_code == 200
    assert "Mechanical engineering placement at Acme" in review_page.text


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

