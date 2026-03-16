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
from playwright.sync_api import Page


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = r"C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe"


def _get_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_server(url: str, timeout_seconds: int = 60) -> None:
    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            response = httpx.get(url, timeout=2.0, trust_env=False)
            if response.status_code == 200:
                return
        except Exception:
            pass
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
        env["SESSION_HTTPS_ONLY"] = "0"

        process = subprocess.Popen(
            [
                PYTHON_EXE,
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
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


class ReviewerPage:
    def __init__(self, page: Page):
        self.page = page

    def goto(self, url: str) -> None:
        self.page.goto(url, wait_until="networkidle")

    def first_set(self):
        return self.page.locator(".set").first

    def second_set(self):
        return self.page.locator(".set").nth(1)

    def fill_manual(self, job: str, cv: str, cover: str, index: int = 0) -> None:
        target = self.page.locator(".set").nth(index)
        target.get_by_label("Job advert text").fill(job)
        target.get_by_label("Paste CV text").fill(cv)
        target.get_by_label("Paste cover letter text").fill(cover)

    def upload_documents(self, cv_path: str, cover_path: str, index: int = 0) -> None:
        target = self.page.locator(".set").nth(index)
        target.get_by_label("Upload CV file").set_input_files(cv_path)
        target.get_by_label("Upload cover letter file").set_input_files(cover_path)

    def submit_review(self) -> None:
        self.page.get_by_role("button", name="Review", exact=True).first.click(no_wait_after=True)

    def wait_for_results(self) -> None:
        self.page.wait_for_selector("text=Scored applications")

    def add_application(self) -> None:
        self.page.get_by_role("button", name="Add another").first.click()

    def sign_in_test_user(self, base_url: str) -> None:
        self.goto(f"{base_url}/test/login?next=/review")

    def open_results_tab(self) -> None:
        self.page.locator('[data-tab-trigger="results"]').click()

    def open_reviewer_tab(self) -> None:
        self.page.locator('[data-tab-trigger="reviewer"]').click()
