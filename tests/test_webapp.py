from fastapi.testclient import TestClient

from getmeajob.webapp import app


client = TestClient(app)


def test_index_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Find the role. Review the application. Move faster." in response.text
    assert "Official company-hosted UK engineering roles" in response.text
    assert "roles shown" in response.text
    assert "Reviewer and results" in response.text


def test_healthz_returns_ok() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_review_submission_renders_results() -> None:
    response = client.post(
        "/",
        data={
            "job": "Mechanical engineering year in industry role. Company: Acme. Need CAD, teamwork, manufacturing.",
            "job_url": "",
        },
        files=[
            ("cv_file", ("cv.txt", b"Mechanical engineering student with CAD and manufacturing project experience. Improved fixture setup by 12%.", "text/plain")),
            ("cover_letter_file", ("cover.txt", b"I want to join Acme for this mechanical engineering year in industry role. I led a design project and delivered measurable results.", "text/plain")),
        ],
    )

    assert response.status_code == 200
    assert "Results" in response.text
    assert "Application 1" in response.text
    assert "Review complete." in response.text
    assert "Review Assistant" in response.text
    assert "Question" in response.text
    assert "Jobs Board" in response.text
    assert "Roles that fit this CV" in response.text


def test_incomplete_submission_preserves_input_and_shows_feedback() -> None:
    response = client.post(
        "/",
        data={
            "job": "Mechanical engineering placement focused on CAD and manufacturing.",
            "job_url": "",
        },
    )

    assert response.status_code == 200
    assert "Needs input" in response.text
    assert "Upload a CV file in .txt, .pdf, or .docx format." in response.text
    assert "Upload a cover letter file in .txt, .pdf, or .docx format." in response.text
    assert "Mechanical engineering placement focused on CAD and manufacturing." in response.text
    assert "Review complete." in response.text


def test_file_upload_submission_renders_results() -> None:
    response = client.post(
        "/",
        data={
            "job": "Mechanical engineering placement. Company: Acme. Need CAD and testing.",
            "job_url": "",
        },
        files=[
            ("cv_file", ("cv.txt", b"Mechanical engineering student with CAD testing and prototype work.", "text/plain")),
            (
                "cover_letter_file",
                ("cover.txt", b"I want to join Acme for this placement and have delivered testing improvements.", "text/plain"),
            ),
        ],
    )

    assert response.status_code == 200
    assert "Results" in response.text
    assert "Application 1" in response.text
    assert "CV markup" in response.text
    assert "issue-suggestion" in response.text
    assert "Roles that fit this CV" in response.text


def test_cached_documents_can_be_reused_without_reupload() -> None:
    response = client.post(
        "/",
        data={
            "job": "Mechanical engineering placement. Company: Acme. Need CAD and testing.",
            "job_url": "",
        },
        files=[
            ("cv_file", ("cv.txt", b"Mechanical engineering student with CAD testing and prototype work.", "text/plain")),
            ("cover_letter_file", ("cover.txt", b"I want to join Acme and have delivered testing improvements.", "text/plain")),
        ],
    )

    assert response.status_code == 200
    assert 'name="cv_cached_text"' in response.text
    assert 'name="cover_cached_text"' in response.text
    assert "Loaded and reusable: cv.txt" in response.text

    second = client.post(
        "/",
        data={
            "job": "Mechanical engineering placement. Company: Acme. Need CAD, testing, and analysis.",
            "job_url": "",
            "cv_cached_text": "Mechanical engineering student with CAD testing and prototype work.",
            "cover_cached_text": "I want to join Acme and have delivered testing improvements.",
            "cv_cached_name": "cv.txt",
            "cover_cached_name": "cover.txt",
        },
    )

    assert second.status_code == 200
    assert "Results" in second.text
    assert "Loaded and reusable: cv.txt" in second.text
    assert "Loaded and reusable: cover.txt" in second.text
