from __future__ import annotations

from getmeajob.interview_prep import build_interview_prep


def test_interview_prep_fallback_builds_grounded_sections() -> None:
    application = {
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

    prep = build_interview_prep(application, [], live_research=False)

    assert prep["company"] == "Acme"
    assert prep["role_title"].startswith("Mechanical engineering placement")
    assert len(prep["process_stages"]) >= 3
    assert len(prep["company_signals"]) >= 1
    assert len(prep["question_groups"]) == 3
    assert len(prep["questions_to_ask"]) >= 2
    assert len(prep["prep_priorities"]) >= 2


def test_interview_prep_live_mode_uses_official_stage_and_signal_clues(monkeypatch) -> None:
    application = {
        "job": "Graduate Software Engineer at Monzo. Need Python, APIs, testing, and cloud deployment.",
        "job_url": "https://boards.greenhouse.io/monzo/jobs/12345",
        "profile": "Software Engineering",
        "requirement_evidence": [
            {
                "requirement": "Cloud deployment",
                "status": "weak",
                "target_line": "Need Python, APIs, testing, and cloud deployment.",
                "cv_evidence": ["Deployed university projects to AWS."],
                "cover_evidence": [],
            }
        ],
        "interview_questions": ["Walk me through your strongest API project and the trade-offs you made."],
    }

    def fake_collect(context: dict[str, str]):
        assert context["company"] == "Monzo"
        return (
            [
                {
                    "title": "Interviewing at Monzo",
                    "url": "https://monzo.com/blog/interviewing-at-monzo",
                    "domain": "monzo.com",
                    "source_title": "Interview process page",
                    "text": (
                        "Our recruiter phone screen covers motivation and impact. "
                        "A technical interview follows with coding and system design. "
                        "The final panel explores collaboration, ownership, and customer thinking."
                    ),
                },
                {
                    "title": "Working at Monzo",
                    "url": "https://monzo.com/careers",
                    "domain": "monzo.com",
                    "source_title": "Careers page",
                    "text": "We care deeply about customers, ownership, and moving quickly with sound judgement.",
                },
            ],
            [
                {
                    "title": "Interviewing at Monzo",
                    "url": "https://monzo.com/blog/interviewing-at-monzo",
                    "source_type": "official_process",
                    "domain": "monzo.com",
                }
            ],
        )

    monkeypatch.setattr("getmeajob.interview_prep._collect_live_research", fake_collect)

    prep = build_interview_prep(application, [], live_research=True)

    assert prep["research_mode"] == "live"
    assert prep["research_confidence"] == "High"
    assert any(stage["confidence"] == "Official source" for stage in prep["process_stages"])
    assert any(signal["title"] == "Customer focus" for signal in prep["company_signals"])
    assert any(group["title"] == "Company-specific questions" for group in prep["question_groups"])
