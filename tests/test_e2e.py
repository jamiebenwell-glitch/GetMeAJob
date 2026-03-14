from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def _get_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_seconds: int = 20) -> None:
    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError(f"Server did not become ready at {url}")


@contextlib.contextmanager
def run_server():
    port = _get_free_port()
    with tempfile.TemporaryDirectory() as temp_dir:
        env = os.environ.copy()
        env["PYTHONPATH"] = "src"
        env["TESTING"] = "1"
        env["GETMEAJOB_DB_PATH"] = str(Path(temp_dir) / "test_app.db")

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "getmeajob.webapp:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=ROOT,
            env=env,
        )

        try:
            base_url = f"http://127.0.0.1:{port}"
            _wait_for_server(f"{base_url}/healthz")
            yield base_url
        finally:
            process.terminate()
            process.wait(timeout=10)


def test_browser_jobs_filters_and_handoff() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{base_url}/jobs", wait_until="networkidle")

        page.get_by_placeholder("Search title, company, location, summary").fill("zzzz-no-match")
        page.wait_for_selector("text=No jobs match the current filters.")
        page.get_by_role("button", name="Reset filters").click()
        page.get_by_label("Source filter").select_option("greenhouse")
        page.wait_for_selector("text=roles shown")
        page.locator(".job-card:not(.hidden)").first.get_by_role("button", name="Open in reviewer").click()

        page.wait_for_url(f"{base_url}/review")
        assert page.locator('textarea[name="job"]').first.input_value().strip() != ""
        assert page.locator('input[name="job_url"]').first.input_value().startswith("https://")
        browser.close()


def test_browser_signed_in_draft_save_and_load() -> None:
    with run_server() as base_url, tempfile.TemporaryDirectory() as temp_dir, sync_playwright() as playwright:
        temp_path = Path(temp_dir)
        cv_path = temp_path / "cv.txt"
        cover_path = temp_path / "cover.txt"
        cv_path.write_text("Mechanical engineering student with CAD, manufacturing, and test rig work.", encoding="utf-8")
        cover_path.write_text("I want to join an engineering team and contribute to testing and manufacturing.", encoding="utf-8")

        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{base_url}/test/login?next=/review", wait_until="networkidle")

        first_set = page.locator(".set").first
        first_set.get_by_label("Upload CV").set_input_files(str(cv_path))
        first_set.get_by_label("Upload cover letter").set_input_files(str(cover_path))
        page.wait_for_selector("text=Loaded from upload: cv.txt")
        page.get_by_role("button", name="Save CV draft").click()
        page.wait_for_selector("text=Saved")
        page.get_by_role("button", name="Save cover draft").click()
        page.wait_for_selector("text=Saved")
        page.wait_for_selector("text=Use draft")

        page.get_by_role("button", name="Add another").first.click()
        second_set = page.locator(".set").nth(1)
        second_set.scroll_into_view_if_needed()
        page.locator('[data-draft-list="cv"] .load-draft').first.click()
        assert second_set.get_by_label("CV text").input_value().startswith("Mechanical engineering student")
        page.locator('[data-draft-list="cover_letter"] .load-draft').first.click()
        assert second_set.get_by_label("Cover letter text").input_value().startswith("I want to join")
        browser.close()


def test_browser_review_results_and_history() -> None:
    with run_server() as base_url, tempfile.TemporaryDirectory() as temp_dir, sync_playwright() as playwright:
        temp_path = Path(temp_dir)
        cv_path = temp_path / "cv.txt"
        cover_path = temp_path / "cover.txt"
        cv_path.write_text(
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            encoding="utf-8",
        )
        cover_path.write_text(
            "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
            encoding="utf-8",
        )

        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{base_url}/test/login?next=/review", wait_until="networkidle")

        first_set = page.locator(".set").first
        first_set.get_by_label("Job advert text").fill(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis."
        )
        first_set.get_by_label("Upload CV").set_input_files(str(cv_path))
        first_set.get_by_label("Upload cover letter").set_input_files(str(cover_path))
        page.get_by_role("button", name="Review", exact=True).first.click(no_wait_after=True)

        page.wait_for_selector("text=Scored applications")
        assert page.locator('[data-tab-trigger="results"]').get_attribute("aria-selected") == "true"
        page.wait_for_selector("text=Roles that fit this CV")
        page.get_by_label("Question").fill("What should I change first?")
        page.get_by_role("button", name="Ask").click()
        page.wait_for_selector("text=Start with")
        page.locator('[data-tab-trigger="reviewer"]').click()
        page.wait_for_selector("text=Score trend")
        assert page.locator(".history-item").count() >= 1
        browser.close()


def test_browser_split_page_layout_desktop_and_mobile() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        desktop_jobs = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop_jobs.goto(f"{base_url}/jobs", wait_until="networkidle")
        assert desktop_jobs.locator(".jobs-page-panel").is_visible()
        assert not desktop_jobs.locator(".review-sidebar").count()
        desktop_jobs_overflow = desktop_jobs.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert desktop_jobs_overflow <= 2

        desktop_review = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop_review.goto(f"{base_url}/review", wait_until="networkidle")
        assert desktop_review.locator(".review-sidebar").is_visible()
        assert desktop_review.locator(".workspace-panel").is_visible()
        desktop_review_overflow = desktop_review.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert desktop_review_overflow <= 2

        mobile_review = browser.new_page(viewport={"width": 390, "height": 1200})
        mobile_review.goto(f"{base_url}/review", wait_until="networkidle")
        mobile_overflow = mobile_review.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert mobile_overflow <= 2
        sidebar_box = mobile_review.locator(".review-sidebar").bounding_box()
        workspace_box = mobile_review.locator(".workspace-panel").bounding_box()
        assert sidebar_box is not None and workspace_box is not None
        assert workspace_box["y"] > sidebar_box["y"]

        browser.close()

