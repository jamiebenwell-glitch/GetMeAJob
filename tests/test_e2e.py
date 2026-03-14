from __future__ import annotations

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


def test_browser_review_flow() -> None:
    port = _get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

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
        _wait_for_server(f"http://127.0.0.1:{port}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cv_path = temp_path / "cv.txt"
            cover_path = temp_path / "cover.txt"
            cv_path.write_text(
                "Mechanical engineering student with CAD, manufacturing, and test rig work. Improved setup time by 15%.",
                encoding="utf-8",
            )
            cover_path.write_text(
                "I want to join Acme for this placement. I delivered testing improvements and built CAD models.",
                encoding="utf-8",
            )

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page()
                page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")

                page.get_by_placeholder("Search title, company, location, summary").fill("zzzz-no-match")
                page.wait_for_selector("text=No jobs match the current filters.")
                page.get_by_placeholder("Search title, company, location, summary").fill("")
                page.wait_for_selector("text=roles shown")
                page.get_by_label("Source filter").select_option("greenhouse")
                assert "shown" in page.locator("#jobs-count").text_content()
                page.get_by_label("Source filter").select_option("")
                page.get_by_label("Remote only").check()
                page.wait_for_selector("text=roles shown")
                page.get_by_label("Remote only").uncheck()

                page.get_by_role("button", name="Add another").click()
                second_job = page.locator(".set").nth(1).get_by_label("Job advert URL")
                second_job.scroll_into_view_if_needed()
                page.get_by_placeholder("Search title, company, location, summary").fill("engineer")
                page.locator(".job-card:not(.hidden)").first.get_by_role("button", name="Load into reviewer").click()
                assert second_job.input_value()
                page.locator(".set").nth(1).get_by_label("Job description").fill(
                    "Mechanical engineering placement. Company: Acme. Need CAD, manufacturing, testing, analysis."
                )
                page.locator(".set").nth(1).get_by_label("CV file").set_input_files(str(cv_path))
                page.locator(".set").nth(1).get_by_label("Cover letter file").set_input_files(str(cover_path))
                page.get_by_role("button", name="Review", exact=True).click(no_wait_after=True)

                page.wait_for_selector("#workspace-results")
                assert page.locator('[data-tab-trigger="results"]').get_attribute("aria-selected") == "true"
                page.wait_for_selector("text=CV markup")
                page.wait_for_selector("text=Matched keywords")
                page.wait_for_selector("text=Roles that fit this CV")
                page.wait_for_selector('[data-result-target="2"]')
                page.get_by_label("Application", exact=True).select_option("2")
                page.get_by_label("Question").fill("What should I change first?")
                page.get_by_role("button", name="Ask").click()
                page.wait_for_selector("text=Start with")
                page.locator('[data-tab-trigger="reviewer"]').click()
                page.locator(".set").nth(1).get_by_label("Job description").fill(
                    "Mechanical engineering placement. Company: Acme. Need CAD, testing, analysis, production."
                )
                page.get_by_role("button", name="Review", exact=True).click(no_wait_after=True)
                page.locator('[data-tab-trigger="reviewer"]').click()
                page.wait_for_selector("text=Loaded and reusable: cv.txt")
                assert "cad" in page.content().lower()
                browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_browser_validation_feedback() -> None:
    port = _get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

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
        _wait_for_server(f"http://127.0.0.1:{port}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            page.get_by_role("button", name="Review", exact=True).click(no_wait_after=True)
            page.wait_for_selector("text=Needs input")
            page.wait_for_selector("text=Upload a CV file in .txt, .pdf, or .docx format.")
            page.wait_for_selector("text=Upload a cover letter file in .txt, .pdf, or .docx format.")
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_browser_layout_smoke_desktop_and_mobile() -> None:
    port = _get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

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
        _wait_for_server(f"http://127.0.0.1:{port}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()

            desktop = browser.new_page(viewport={"width": 1440, "height": 1200})
            desktop.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            assert desktop.locator(".workspace").is_visible()
            assert desktop.locator(".jobs-panel").is_visible()
            assert desktop.locator(".workspace-panel").is_visible()
            desktop_overflow = desktop.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert desktop_overflow <= 2

            mobile = browser.new_page(viewport={"width": 390, "height": 1200})
            mobile.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")
            mobile_overflow = mobile.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
            assert mobile_overflow <= 2

            first_filter = mobile.locator(".job-filters > *").nth(0).bounding_box()
            second_filter = mobile.locator(".job-filters > *").nth(1).bounding_box()
            assert first_filter is not None and second_filter is not None
            assert second_filter["y"] > first_filter["y"]

            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_browser_new_application_stays_reachable() -> None:
    port = _get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

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
        _wait_for_server(f"http://127.0.0.1:{port}")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")

            page.get_by_role("button", name="Add another").click()
            second_set = page.locator(".set").nth(1)
            second_job_url = second_set.get_by_label("Job advert URL")
            second_job_url.scroll_into_view_if_needed()
            assert second_job_url.is_visible()
            assert page.locator(".set.active").nth(0).locator("h2, h3").text_content() == "Application 2"

            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)


def test_browser_results_stay_in_workspace() -> None:
    port = _get_free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

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
        _wait_for_server(f"http://127.0.0.1:{port}")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cv_path = temp_path / "cv.txt"
            cover_path = temp_path / "cover.txt"
            cv_path.write_text("Mechanical engineering student with CAD, testing, and manufacturing project work.", encoding="utf-8")
            cover_path.write_text("I want to join Acme and can contribute to testing and manufacturing support.", encoding="utf-8")

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(viewport={"width": 1440, "height": 1200})
                page.goto(f"http://127.0.0.1:{port}", wait_until="networkidle")

                page.locator(".set").nth(0).get_by_label("Job description").fill(
                    "Mechanical engineering placement. Company: Acme. Need CAD, testing, manufacturing, analysis."
                )
                page.locator(".set").nth(0).get_by_label("CV file").set_input_files(str(cv_path))
                page.locator(".set").nth(0).get_by_label("Cover letter file").set_input_files(str(cover_path))
                page.get_by_role("button", name="Review", exact=True).click(no_wait_after=True)

                page.wait_for_selector("text=Review studio")
                assert page.locator('[data-tab-trigger="results"]').get_attribute("aria-selected") == "true"
                assert page.locator("#workspace-results").is_visible()
                workspace_box = page.locator(".workspace-panel").bounding_box()
                results_box = page.locator("#workspace-results").bounding_box()
                assert workspace_box is not None and results_box is not None
                assert results_box["y"] < workspace_box["y"] + workspace_box["height"]
                page.wait_for_selector("text=Roles that fit this CV")

                browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
