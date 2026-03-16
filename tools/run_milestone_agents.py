from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import os
import sys
import tempfile
import time
import traceback

from PIL import Image, ImageChops
from playwright.sync_api import Browser, Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from tests.e2e_helpers import ReviewerPage, run_server  # noqa: E402


VISUAL_BASELINE_DIR = ROOT / "tests" / "visual_baselines"
VISUAL_OUTPUT_DIR = ROOT / "data" / "visual_regression"
UPDATE_VISUAL_BASELINES = "--update-visual-baselines" in sys.argv or os.getenv("UPDATE_VISUAL_BASELINES") == "1"
MAX_VISUAL_DIFF_RATIO = 0.0015


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class AgentResult:
    name: str
    passed: bool
    duration_seconds: float
    checks: list[CheckResult] = field(default_factory=list)
    error: str = ""


class MilestoneAgent:
    name = "unnamed-agent"

    def __init__(self) -> None:
        self.checks: list[CheckResult] = []

    def check(self, name: str, fn) -> None:
        try:
            detail = fn() or ""
            self.checks.append(CheckResult(name=name, passed=True, detail=str(detail)))
        except Exception as exc:  # pragma: no cover - exercised by the milestone harness directly
            self.checks.append(CheckResult(name=name, passed=False, detail=str(exc)))
            raise

    def run(self, browser: Browser, base_url: str) -> AgentResult:
        start = time.perf_counter()
        try:
            self.execute(browser, base_url)
            return AgentResult(
                name=self.name,
                passed=True,
                duration_seconds=round(time.perf_counter() - start, 2),
                checks=self.checks,
            )
        except Exception:  # pragma: no cover - exercised by the milestone harness directly
            return AgentResult(
                name=self.name,
                passed=False,
                duration_seconds=round(time.perf_counter() - start, 2),
                checks=self.checks,
                error=traceback.format_exc(),
            )

    def execute(self, browser: Browser, base_url: str) -> None:
        raise NotImplementedError


class JobsBoardAgent(MilestoneAgent):
    name = "jobs-board-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto(f"{base_url}/jobs", wait_until="networkidle")

        self.check("jobs layout renders", lambda: page.locator(".jobs-layout").is_visible() or "jobs layout visible")
        self.check("empty-state filtering works", lambda: _jobs_empty_state(page))
        self.check("job handoff opens reviewer", lambda: _jobs_handoff(page, base_url))
        page.close()


def _jobs_empty_state(page: Page) -> str:
    page.get_by_placeholder("Search title, company, location, summary").fill("zzzz-no-match")
    page.wait_for_selector("text=No jobs match the current filters.")
    page.get_by_role("button", name="Reset filters").click()
    page.wait_for_selector("text=roles shown")
    return "filters and reset behaved as expected"


def _jobs_handoff(page: Page, base_url: str) -> str:
    page.get_by_label("Source filter").select_option("greenhouse")
    page.locator(".job-card:not(.hidden)").first.get_by_role("button", name="Open in reviewer").click()
    page.wait_for_url(f"{base_url}/review")
    assert page.locator('textarea[name="job"]').first.input_value().strip()
    assert page.locator('input[name="job_url"]').first.input_value().startswith("https://")
    return "job was loaded into reviewer"


class GuestReviewerAgent(MilestoneAgent):
    name = "guest-reviewer-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")

        self.check("multi-application controls", lambda: _guest_multi_application(page))
        self.check("guest draft save stays safe", lambda: _guest_save_and_review(review, page))
        self.check("validation feedback remains visible", lambda: _guest_validation(page, base_url))
        page.close()


def _guest_multi_application(page: Page) -> str:
    page.get_by_role("button", name="Add another").first.click()
    assert page.locator(".set").count() == 2
    second_set = page.locator(".set").nth(1)
    second_set.get_by_label("Job advert text").fill("Temporary job text to test reset.")
    second_set.get_by_role("button", name="Reset").click()
    assert second_set.get_by_label("Job advert text").input_value() == ""
    second_set.get_by_role("button", name="Remove").click()
    assert page.locator(".set").count() == 1
    return "add, reset, and remove all worked"


def _guest_save_and_review(review: ReviewerPage, page: Page) -> str:
    first_set = review.first_set()
    first_set.get_by_label("Paste CV text").fill(
        "Mechanical engineering student with CAD, testing, and manufacturing project work."
    )
    first_set.get_by_role("button", name="Save CV draft").click()
    page.wait_for_selector("text=Sign in with Google to save drafts.")
    first_set.get_by_label("Job advert text").fill(
        "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis."
    )
    first_set.get_by_label("Paste cover letter text").fill(
        "I want this role because it matches my CAD, testing, and manufacturing work."
    )
    review.submit_review()
    review.wait_for_results()
    assert page.locator(".score").first.is_visible()
    return "guest review still completed after blocked draft save"


def _guest_validation(page: Page, base_url: str) -> str:
    page.goto(f"{base_url}/review", wait_until="networkidle")
    page.evaluate("() => window.localStorage.clear()")
    page.goto(f"{base_url}/review", wait_until="networkidle")
    page.locator('[data-tab-trigger="reviewer"]').click()
    page.locator('.set').first.get_by_label("Job advert text").fill("Mechanical role with CAD and testing.")
    page.get_by_role("button", name="Review", exact=True).first.click()
    page.wait_for_selector("text=Needs input")
    assert page.locator("text=Upload a CV file in .txt, .pdf, or .docx format, or use a saved draft.").is_visible()
    return "validation feedback is visible"


class SignedInWorkspaceAgent(MilestoneAgent):
    name = "signed-in-workspace-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
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

            page = browser.new_page(viewport={"width": 1440, "height": 1200})
            try:
                review = ReviewerPage(page)
                review.sign_in_test_user(base_url)

                self.check("draft upload and save flow", lambda: _signed_in_draft_flow(page, review, str(cv_path), str(cover_path)))
                self.check("review results expose new decision layers", lambda: _signed_in_results_flow(page, review))
                self.check("history outcome and evidence bank persist", lambda: _signed_in_history_and_evidence(page, base_url))
            finally:
                page.close()


def _signed_in_draft_flow(page: Page, review: ReviewerPage, cv_path: str, cover_path: str) -> str:
    review.upload_documents(cv_path, cover_path)
    page.wait_for_selector("text=Loaded from upload: cv.txt")
    page.get_by_role("button", name="Save CV draft").click()
    page.wait_for_selector("text=Draft saved.")
    review.first_set().get_by_label("Paste CV text").fill(
        "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%."
    )
    page.get_by_role("button", name="Save CV draft").click()
    page.wait_for_selector("text=Draft saved.")
    page.get_by_role("button", name="Save cover draft").click()
    page.wait_for_selector("text=Draft saved.")
    page.locator('[data-draft-list="cv"] .view-revisions').first.click()
    page.wait_for_selector("text=CV draft history")
    assert page.locator(".revision-line").count() >= 1
    return "drafts and revisions worked"


def _signed_in_results_flow(page: Page, review: ReviewerPage) -> str:
    review.first_set().get_by_label("Job advert text").fill(
        "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis."
    )
    review.submit_review()
    review.wait_for_results()
    page.wait_for_selector("text=Hiring Manager View")
    page.wait_for_selector("text=Requirement to evidence")
    page.wait_for_selector("text=Parser checks")
    page.wait_for_selector("text=Questions before rewriting")
    page.wait_for_selector("text=Questions you should be ready for")
    assert page.locator(".requirement-card").count() >= 1
    assert page.locator(".ats-check").count() >= 1
    assert page.locator(".tailored-advice-card").count() >= 1
    return "review results exposed verdict, evidence map, ats, follow-up, and interview handoff"


def _signed_in_history_and_evidence(page: Page, base_url: str) -> str:
    page.locator(".history-outcome").first.select_option("interview")
    page.wait_for_timeout(400)
    page.goto(f"{base_url}/review", wait_until="networkidle")
    assert page.locator(".history-outcome").first.input_value() == "interview"
    assert page.locator(".evidence-card").count() >= 1
    page.get_by_role("link", name="Open review").first.click()
    page.wait_for_selector("text=Scored applications")
    assert page.locator(".score").first.text_content().strip().endswith("%")
    return "history outcome and evidence bank persisted"


class AssistantCoachAgent(MilestoneAgent):
    name = "assistant-coach-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I am interested in this role and believe I would be a strong fit for the company and the position.",
        )
        review.submit_review()
        review.wait_for_results()

        self.check("assistant explains first priority", lambda: _ask(page, "What should I change first?", "Start with"))
        self.check("assistant quotes cover letter", lambda: _ask(page, "What should I change in my cover letter?", "In your cover letter you wrote"))
        self.check("assistant explains requirement map", lambda: _ask(page, "Show me the requirement map", "CV evidence:"))
        self.check("assistant asks for grounded follow-up", lambda: _ask(page, "What else do you need from me?", "The next factual questions to answer are"))
        self.check("assistant provides interview handoff", lambda: _ask(page, "What interview questions will they ask?", "Likely interview probes"))
        self.check(
            "assistant refuses invented rewrites",
            lambda: _ask_any(
                page,
                "Rewrite this CV bullet",
                ["Keep the truth of", "I cannot rewrite this credibly yet without inventing evidence"],
            ),
        )
        page.close()


class RequirementSafetyAgent(MilestoneAgent):
    name = "requirement-safety-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            (
                "Graduate Mechanical Engineer. Need CAD, manufacturing, testing, and analysis. "
                "To do this, we must ask applicants and employees if they have a disability or have ever had one."
            ),
            "Mechanical engineering student with CAD, testing, manufacturing, and analysis project work. Improved fixture setup time by 15%.",
            "I want this graduate role because it matches my CAD, testing, and manufacturing experience.",
        )
        review.submit_review()
        review.wait_for_results()

        self.check("requirement cards exclude demographic questionnaire text", lambda: _requirement_cards_stay_safe(page))
        self.check("assistant does not suggest protected-attribute disclosure", lambda: _assistant_stays_safe(page))
        self.check("tailored advice keeps visible role targets", lambda: _tailored_advice_targets_stay_grounded(page))
        page.close()


def _ask(page: Page, question: str, expected: str) -> str:
    page.get_by_label("Question").fill(question)
    page.get_by_role("button", name="Ask").click()
    page.wait_for_selector(f"text={expected}")
    return expected


def _ask_any(page: Page, question: str, expected_options: list[str]) -> str:
    page.get_by_label("Question").fill(question)
    page.get_by_role("button", name="Ask").click()
    end = time.time() + 30
    while time.time() < end:
        content = page.locator("#chatbot-messages").text_content() or ""
        for option in expected_options:
            if option in content:
                return option
        page.wait_for_timeout(300)
    raise AssertionError(f"Expected one of {expected_options!r} in chatbot messages")


def _requirement_cards_stay_safe(page: Page) -> str:
    combined = " ".join(page.locator(".requirement-card").all_inner_texts()).lower()
    for blocked in ("disability", "applicants", "employees", "ever had one"):
        assert blocked not in combined
    return "requirement cards excluded protected-attribute questionnaire text"


def _assistant_stays_safe(page: Page) -> str:
    page.get_by_label("Question").fill("What experience should I add?")
    page.get_by_role("button", name="Ask").click()
    page.wait_for_selector("#chatbot-messages .chat-message.bot")
    combined = (page.locator("#chatbot-messages").text_content() or "").lower()
    assert combined.strip()
    for blocked in ("disability", "applicants", "employees", "ever had one"):
        assert blocked not in combined
    return "assistant stayed grounded on role evidence instead of protected attributes"


def _tailored_advice_targets_stay_grounded(page: Page) -> str:
    targets = " ".join(page.locator(".tailored-advice-targets").all_inner_texts()).lower()
    assert "analysis" in targets
    for blocked in ("disability", "applicants", "employees", "ever had one"):
        assert blocked not in targets
    return "tailored advice stayed focused on role requirements"


class SuggestionsAndBatchAgent(MilestoneAgent):
    name = "suggestions-and-batch-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I want this role because it matches my CAD, testing, and manufacturing work.",
        )
        review.add_application()
        second = review.second_set()
        second.get_by_label("Job advert text").fill("Graduate systems engineer role with controls, analysis, and teamwork.")
        review.submit_review()
        review.wait_for_results()

        self.check("one complete and one incomplete application coexist", lambda: _batch_submission(page))
        self.check("role suggestion reloads reviewer", lambda: _suggestion_handoff(page))
        page.close()


class InterviewPrepAgent(MilestoneAgent):
    name = "interview-prep-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        review = ReviewerPage(page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I want this role because it matches my CAD, testing, and manufacturing work.",
        )
        review.submit_review()
        review.wait_for_results()

        self.check("review flows into interview prep", lambda: _open_interview_prep(page, base_url))
        self.check("interview prep renders sources and question sets", lambda: _validate_interview_prep(page))
        page.close()


def _batch_submission(page: Page) -> str:
    page.locator('[data-tab-trigger="reviewer"]').click()
    page.wait_for_selector("text=Needs input")
    assert page.locator(".score").first.is_visible()
    return "batch review preserved results and validation together"


def _suggestion_handoff(page: Page) -> str:
    page.locator('[data-tab-trigger="results"]').click()
    page.wait_for_selector("text=Roles that fit this CV")
    button = page.locator(".use-suggestion").first
    button.click()
    page.wait_for_selector('[data-tab-trigger="reviewer"][aria-selected="true"]')
    assert page.locator('textarea[name="job"]').first.input_value().strip()
    return "suggestion loaded back into reviewer"


class MobileLayoutAgent(MilestoneAgent):
    name = "mobile-layout-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        jobs_page = browser.new_page(viewport={"width": 390, "height": 1000})
        jobs_page.goto(f"{base_url}/jobs", wait_until="networkidle")
        self.check("jobs page has no horizontal overflow", lambda: _no_overflow(jobs_page, "jobs"))
        jobs_page.close()

        review_page = browser.new_page(viewport={"width": 390, "height": 1200})
        review = ReviewerPage(review_page)
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I want this role because it matches my CAD, testing, and manufacturing work.",
        )
        review.submit_review()
        review.wait_for_results()
        self.check("review page has no horizontal overflow", lambda: _no_overflow(review_page, "review"))
        self.check("result cards fit mobile width", lambda: _card_width(review_page))
        review_page.close()


def _no_overflow(page: Page, label: str) -> str:
    overflow = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert overflow <= 2
    return f"{label} overflow={overflow}"


def _card_width(page: Page) -> str:
    box = page.locator(".result-card").first.bounding_box()
    assert box is not None and box["width"] <= 390
    return f"result card width={box['width']:.1f}"


def _open_interview_prep(page: Page, base_url: str) -> str:
    page.get_by_role("link", name="Interview prep").first.click()
    page.wait_for_url(f"{base_url}/interview-prep")
    page.wait_for_selector("text=What the process probably looks like")
    return "interview prep route opened from review"


def _validate_interview_prep(page: Page) -> str:
    page.wait_for_selector("text=What this company seems to care about")
    page.wait_for_selector("text=Question sets to rehearse")
    assert page.locator(".prep-stage-card").count() >= 1
    assert page.locator(".prep-question-group-card").count() >= 1
    assert page.locator(".prep-source-card").count() >= 1 or page.locator("#prep-sources-list .sidebar-empty").count() >= 1
    return "interview prep rendered stage cards, question groups, and source state"


class VisualRegressionAgent(MilestoneAgent):
    name = "visual-regression-agent"

    def execute(self, browser: Browser, base_url: str) -> None:
        VISUAL_BASELINE_DIR.mkdir(parents=True, exist_ok=True)
        VISUAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self.check("jobs empty-state snapshot", lambda: _capture_jobs_empty_state(browser, base_url))
        self.check("review workspace snapshot", lambda: _capture_review_workspace(browser, base_url))
        self.check("review results snapshot", lambda: _capture_review_results(browser, base_url, mobile=False))
        self.check("review results mobile snapshot", lambda: _capture_review_results(browser, base_url, mobile=True))
        self.check("interview prep snapshot", lambda: _capture_interview_prep(browser, base_url))


def _compare_snapshot(name: str, image_bytes: bytes) -> str:
    baseline_path = VISUAL_BASELINE_DIR / f"{name}.png"
    actual_path = VISUAL_OUTPUT_DIR / f"{name}.png"
    actual_path.write_bytes(image_bytes)

    if UPDATE_VISUAL_BASELINES or not baseline_path.exists():
        baseline_path.write_bytes(image_bytes)
        return f"baseline {'updated' if UPDATE_VISUAL_BASELINES else 'created'}"

    with Image.open(baseline_path) as baseline_image, Image.open(actual_path) as actual_image:
        baseline = baseline_image.convert("RGBA")
        actual = actual_image.convert("RGBA")
        if baseline.size != actual.size:
            raise AssertionError(f"snapshot size changed from {baseline.size} to {actual.size}")

        diff = ImageChops.difference(baseline, actual)
        bbox = diff.getbbox()
        if bbox is None:
            return "no diff"

        grayscale = diff.convert("L")
        changed_pixels = sum(1 for value in grayscale.getdata() if value)
        ratio = changed_pixels / float(baseline.size[0] * baseline.size[1])
        if ratio > MAX_VISUAL_DIFF_RATIO:
            diff_path = VISUAL_OUTPUT_DIR / f"{name}.diff.png"
            diff.save(diff_path)
            raise AssertionError(f"visual diff ratio {ratio:.5f} exceeded {MAX_VISUAL_DIFF_RATIO:.5f}")
        return f"minor diff ratio {ratio:.5f}"


def _stable_screenshot(locator, name: str) -> str:
    image_bytes = locator.screenshot(animations="disabled", caret="hide", scale="css")
    return _compare_snapshot(name, image_bytes)


def _capture_jobs_empty_state(browser: Browser, base_url: str) -> str:
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        page.goto(f"{base_url}/jobs", wait_until="networkidle")
        page.get_by_placeholder("Search title, company, location, summary").fill("zzzz-no-match")
        page.wait_for_selector("text=No jobs match the current filters.")
        return _stable_screenshot(page.locator(".jobs-layout"), "jobs_empty_state_desktop")
    finally:
        page.close()


def _capture_review_workspace(browser: Browser, base_url: str) -> str:
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    try:
        page.goto(f"{base_url}/review", wait_until="networkidle")
        page.evaluate("() => window.localStorage.clear()")
        page.goto(f"{base_url}/review", wait_until="networkidle")
        return _stable_screenshot(page.locator(".review-layout"), "review_workspace_desktop")
    finally:
        page.close()


def _capture_review_results(browser: Browser, base_url: str, mobile: bool) -> str:
    viewport = {"width": 390, "height": 1200} if mobile else {"width": 1440, "height": 1200}
    page = browser.new_page(viewport=viewport)
    review = ReviewerPage(page)
    try:
        review.goto(f"{base_url}/review")
        page.evaluate("() => window.localStorage.clear()")
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I want this role because it matches my CAD, testing, and manufacturing work.",
        )
        review.submit_review()
        review.wait_for_results()
        page.wait_for_selector("text=Hiring Manager View")
        snapshot_name = "review_results_mobile" if mobile else "review_results_desktop"
        return _stable_screenshot(page.locator(".result-card").first, snapshot_name)
    finally:
        page.close()


def _capture_interview_prep(browser: Browser, base_url: str) -> str:
    page = browser.new_page(viewport={"width": 1440, "height": 1200})
    review = ReviewerPage(page)
    try:
        review.goto(f"{base_url}/review")
        page.evaluate("() => window.localStorage.clear()")
        review.goto(f"{base_url}/review")
        review.fill_manual(
            "Mechanical engineering placement at Acme. Need CAD, manufacturing, testing, and analysis.",
            "Mechanical engineering student with CAD, prototype testing, and manufacturing project work. Improved setup time by 15%.",
            "I want this role because it matches my CAD, testing, and manufacturing work.",
        )
        review.submit_review()
        review.wait_for_results()
        page.get_by_role("link", name="Interview prep").first.click()
        page.wait_for_url(f"{base_url}/interview-prep")
        page.wait_for_selector("text=What the process probably looks like")
        return _stable_screenshot(page.locator(".prep-layout"), "interview_prep_desktop")
    finally:
        page.close()


def run_milestone_agents() -> dict[str, object]:
    agents = [
        JobsBoardAgent(),
        GuestReviewerAgent(),
        SignedInWorkspaceAgent(),
        AssistantCoachAgent(),
        RequirementSafetyAgent(),
        SuggestionsAndBatchAgent(),
        InterviewPrepAgent(),
        MobileLayoutAgent(),
        VisualRegressionAgent(),
    ]

    started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    start = time.perf_counter()
    with run_server() as base_url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            results = [agent.run(browser, base_url) for agent in agents]
        finally:
            browser.close()

    passed = all(result.passed for result in results)
    return {
        "started_at": started_at,
        "base_url": base_url,
        "passed": passed,
        "duration_seconds": round(time.perf_counter() - start, 2),
        "agents": [asdict(result) for result in results],
    }


def main() -> int:
    report = run_milestone_agents()
    target = ROOT / "data" / "milestone_test_report.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(target)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
