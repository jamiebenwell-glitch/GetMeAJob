from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright


def note(message: str) -> None:
    print(message)


def main() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.on("pageerror", lambda exc: note(f"PAGEERROR {exc}"))
        page.on("console", lambda msg: note(f"CONSOLE {msg.type}: {msg.text}"))

        page.goto("https://getmeajob-yvur.onrender.com/jobs", wait_until="networkidle")
        note("jobs loaded")
        page.get_by_role("button", name="Open in reviewer").first.click()
        page.wait_for_url("**/review")
        job_url = page.locator('input[name="job_url"]').first.input_value()
        job_text = page.locator('textarea[name="job"]').first.input_value()
        note(f"handoff job_url populated={bool(job_url)} job_text_populated={bool(job_text.strip())}")

        page.get_by_role("button", name="Add another").first.click()
        note(f'after add count={page.locator(".set").count()}')
        second = page.locator(".set").nth(1)
        second.get_by_role("button", name="Remove").click()
        note(f'after remove count={page.locator(".set").count()}')

        first = page.locator(".set").first
        first.get_by_role("button", name="Reset").click()
        reset_job_url = first.locator('input[name="job_url"]').input_value()
        reset_job_text = first.locator('textarea[name="job"]').input_value()
        note(f"after reset job_url_empty={reset_job_url == ''} job_text_empty={reset_job_text == ''}")

        first.get_by_label("Paste CV text").fill(
            "Mechanical engineering student with CAD, testing, and manufacturing project work."
        )
        first.get_by_role("button", name="Save CV draft").click()
        page.wait_for_load_state("networkidle")
        note(f"after guest save draft url={page.url}")

        if "/auth/login/google" in page.url:
            page.go_back(wait_until="networkidle")
            note(f"after back url={page.url}")

        first = page.locator(".set").first
        first.get_by_label("Job advert text").fill(
            "Mechanical Design Engineer. Must have CAD, testing, manufacturing, and analysis experience. Preferred FEA experience."
        )
        first.get_by_label("Paste CV text").fill(
            "Mechanical engineering student with CAD, testing, manufacturing, and design project work. Improved prototype setup by 20%."
        )
        first.get_by_label("Paste cover letter text").fill(
            "I want this design role because it matches my CAD and manufacturing project experience."
        )
        page.get_by_role("button", name="Review", exact=True).first.click()
        page.wait_for_load_state("networkidle")
        note(f'after review results_visible={page.locator("text=Scored applications").count() > 0}')
        if page.locator(".score").count():
            note(f'score={page.locator(".score").first.text_content()}')

        if page.locator('[data-tab-trigger="results"]').count():
            page.locator('[data-tab-trigger="results"]').click()
            note("clicked results tab")
        if page.locator("#chatbot-question").count():
            page.locator("#chatbot-question").fill("What should I change first?")
            page.get_by_role("button", name="Ask").click()
            try:
                page.wait_for_selector("text=Start with", timeout=5000)
                note("chatbot responded with Start with")
            except PWTimeout:
                note("chatbot did not produce expected response")

        if page.locator(".use-suggestion").count():
            page.locator(".use-suggestion").first.click()
            page.locator('[data-tab-trigger="reviewer"]').click()
            loaded_job = page.locator('textarea[name="job"]').first.input_value()
            note(f"suggestion loaded into reviewer={bool(loaded_job.strip())}")
        else:
            note("no suggestion button visible")

        browser.close()


if __name__ == "__main__":
    main()
