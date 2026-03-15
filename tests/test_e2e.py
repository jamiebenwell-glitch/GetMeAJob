from __future__ import annotations

import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

from tests.e2e_helpers import ReviewerPage, run_server


def test_browser_jobs_filters_and_handoff() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{base_url}/jobs", wait_until="networkidle")

        assert page.locator(".jobs-filter-panel").is_visible()
        assert page.locator(".jobs-results-panel").is_visible()
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


def test_browser_review_supports_manual_text_entry() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")

        first_set = review.first_set()
        assert first_set.get_by_label("Paste CV text").is_visible()
        assert first_set.get_by_label("Paste cover letter text").is_visible()
        assert first_set.get_by_label("Upload CV file").is_visible()
        assert first_set.get_by_label("Upload cover letter file").is_visible()

        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, testing, and prototype project work. Improved fixture setup by 15%.",
            "I want to join Acme for this placement and can support CAD, testing, and manufacturing delivery.",
        )
        review.submit_review()
        review.wait_for_results()

        assert page.locator('[data-tab-trigger="results"]').get_attribute("aria-selected") == "true"
        page.locator('[data-tab-trigger="reviewer"]').click()
        assert first_set.get_by_label("Paste CV text").input_value().startswith("Mechanical engineering student")
        assert first_set.get_by_label("Paste cover letter text").input_value().startswith("I want to join Acme")
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
        review = ReviewerPage(page)
        review.sign_in_test_user(base_url)

        review.upload_documents(str(cv_path), str(cover_path))
        page.wait_for_selector("text=Loaded from upload: cv.txt")
        page.get_by_role("button", name="Save CV draft").click()
        page.wait_for_selector("text=Saved")
        review.first_set().get_by_label("Paste CV text").fill(
            "Mechanical engineering student with CAD, manufacturing, and test rig work.\nImproved setup time by 15%."
        )
        page.get_by_role("button", name="Save CV draft").click()
        page.wait_for_selector("text=Saved")
        page.get_by_role("button", name="Save cover draft").click()
        page.wait_for_selector("text=Saved")
        page.wait_for_selector("text=Use draft")
        page.locator('[data-draft-list="cv"] .view-revisions').first.click()
        page.wait_for_selector("text=CV draft history")
        page.wait_for_selector("text=added")
        assert page.locator(".revision-line.added").count() >= 1

        review.add_application()
        second_set = review.second_set()
        second_set.scroll_into_view_if_needed()
        page.locator('[data-draft-list="cv"] .load-draft').first.click()
        assert second_set.get_by_label("Paste CV text").input_value().startswith("Mechanical engineering student")
        page.locator('[data-draft-list="cover_letter"] .load-draft').first.click()
        assert second_set.get_by_label("Paste cover letter text").input_value().startswith("I want to join")
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
        review = ReviewerPage(page)
        review.sign_in_test_user(base_url)

        review.first_set().get_by_label("Job advert text").fill(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis."
        )
        review.upload_documents(str(cv_path), str(cover_path))
        review.submit_review()

        review.wait_for_results()
        assert page.locator('[data-tab-trigger="results"]').get_attribute("aria-selected") == "true"
        assert page.locator(".result-overview-grid").is_visible()
        assert page.locator(".results-side-column .markup-card").count() >= 2
        assert int(page.locator(".score").first.text_content().strip().rstrip("%")) >= 60
        page.wait_for_selector("text=Roles that fit this CV")
        page.wait_for_selector(".issue-card")
        assert page.locator(".issue-card").count() >= 2
        assert page.locator(".issue-action-label").first.text_content() == "What to change"
        issue_card_box = page.locator(".issue-card").first.bounding_box()
        workspace_box = page.locator(".workspace-panel").bounding_box()
        assert issue_card_box is not None and workspace_box is not None
        assert issue_card_box["x"] >= workspace_box["x"]
        assert issue_card_box["x"] + issue_card_box["width"] <= workspace_box["x"] + workspace_box["width"] + 2
        red_color = page.locator(".issue-suggestion").first.evaluate(
            "(el) => window.getComputedStyle(el).color"
        )
        assert red_color in {"rgb(180, 35, 24)", "rgb(180, 35, 24)"}
        page.get_by_label("Question").fill("What should I change first?")
        page.get_by_role("button", name="Ask").click()
        page.wait_for_selector("text=Start with")
        review.open_reviewer_tab()
        page.wait_for_selector("text=Score trend")
        assert page.locator("#history-chart svg").is_visible()
        assert page.locator(".history-item").count() >= 1
        browser.close()


def test_browser_split_page_layout_desktop_and_mobile() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()

        desktop_jobs = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop_jobs.goto(f"{base_url}/jobs", wait_until="networkidle")
        assert desktop_jobs.locator(".page-intro.jobs-intro").is_visible()
        assert desktop_jobs.locator(".jobs-layout").is_visible()
        assert desktop_jobs.locator(".jobs-page-panel").is_visible()
        assert not desktop_jobs.locator(".review-sidebar").count()
        desktop_jobs_overflow = desktop_jobs.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert desktop_jobs_overflow <= 2

        desktop_review = browser.new_page(viewport={"width": 1440, "height": 1200})
        desktop_review.goto(f"{base_url}/review", wait_until="networkidle")
        assert desktop_review.locator(".page-intro.review-intro").is_visible()
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


def test_browser_markup_cards_stay_readable_on_mobile() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD and student team experience.",
            "I am interested in this role and believe I would be a strong fit for the company and the position.",
        )
        review.submit_review()
        review.wait_for_results()

        page.wait_for_selector(".issue-card")
        mobile_overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        assert mobile_overflow <= 2
        first_issue = page.locator(".issue-card").first.bounding_box()
        assert first_issue is not None
        assert first_issue["width"] <= 390
        browser.close()


def test_browser_review_keeps_senior_mismatch_score_low() -> None:
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Senior Software Engineer. Build backend APIs, cloud services, and distributed systems. Requires 5+ years of software engineering experience.",
            "Mechanical engineering undergraduate with CAD, testing, and manufacturing project experience. Completed a year in industry.",
            "I am an undergraduate student and I want to apply because I am interested in software and engineering.",
        )
        review.submit_review()
        review.wait_for_results()

        assert int(page.locator(".score").first.text_content().strip().rstrip("%")) <= 35
        browser.close()
