from __future__ import annotations

from copy import deepcopy


BASE_REVIEWER_CASES = [
    {
        "name": "mechanical_placement_strong_fit",
        "job": "Mechanical Engineering Placement. Need CAD, manufacturing, testing, and analysis support across prototype builds.",
        "cv": "Mechanical engineering student with SolidWorks CAD, prototype testing, and manufacturing project work. Improved fixture setup time by 15%.",
        "cover": "I want this placement because it matches my CAD, testing, and manufacturing experience from projects and lab work.",
        "score_min": 65,
        "score_max": 90,
        "must_include": ["cad", "testing"],
    },
    {
        "name": "software_graduate_good_fit",
        "job": "Graduate Software Engineer. Build backend APIs, write tests, and deploy services in Python and AWS.",
        "cv": "Computer science finalist with Python, REST APIs, SQL, AWS coursework, and a web app internship. Built tested backend services.",
        "cover": "I want this graduate software role because I have already built Python APIs, written tests, and deployed coursework to AWS.",
        "score_min": 62,
        "score_max": 88,
        "must_include": ["python", "api"],
    },
    {
        "name": "undergrad_vs_senior_software",
        "job": "Senior Software Engineer. Own distributed backend systems and mentor engineers. Requires 5+ years of software engineering experience.",
        "cv": "Mechanical engineering undergraduate with CAD, testing, and manufacturing project experience. Completed a year in industry.",
        "cover": "I am an undergraduate student and I am interested in software and engineering.",
        "score_min": 8,
        "score_max": 35,
        "must_note": "senior",
    },
    {
        "name": "generic_cover_letter_penalty",
        "job": "Mechanical Design Engineer. Need CAD, design for manufacture, testing, and analysis.",
        "cv": "Mechanical engineering student with CAD, test rig work, and prototype manufacture. Reduced rework by 12%.",
        "cover": "I am excited by this opportunity and believe I would be a strong fit for your company.",
        "score_min": 45,
        "score_max": 75,
        "must_note": "cover letter",
    },
    {
        "name": "strong_cover_weak_cv",
        "job": "Manufacturing Placement. Need process improvement, testing, lean, and data analysis.",
        "cv": "Engineering student involved in society activities and teamwork.",
        "cover": "In my placement search I have focused on manufacturing, testing, lean, and data analysis and I want to build that experience further.",
        "score_min": 20,
        "score_max": 55,
        "must_note": "evidence",
    },
    {
        "name": "electrical_to_mechanical_mismatch",
        "job": "Mechanical Engineer. Need CAD, tolerance analysis, and manufacturing support.",
        "cv": "Electrical engineering student with PCB layout, embedded C, and circuit testing experience.",
        "cover": "I want to work in hardware engineering and bring my electronics experience to the team.",
        "score_min": 8,
        "score_max": 40,
        "must_note": "different disciplines",
    },
    {
        "name": "data_role_partial_fit",
        "job": "Data Analyst Graduate. Need SQL, dashboards, Python, and stakeholder communication.",
        "cv": "Mathematics finalist with Python, SQL, dashboards, and internship reporting work. Presented findings to operations managers.",
        "cover": "I want this graduate analyst role because I enjoy turning SQL and Python work into useful stakeholder reporting.",
        "score_min": 60,
        "score_max": 88,
        "must_include": ["sql", "python"],
    },
    {
        "name": "civil_role_mismatch",
        "job": "Graduate Civil Engineer. Support structural design, infrastructure planning, and site coordination.",
        "cv": "Mechanical engineering student with CAD, FEA, and prototype manufacture experience.",
        "cover": "I am applying for this engineering role because I enjoy design and analysis.",
        "score_min": 8,
        "score_max": 42,
        "must_note": "different disciplines",
    },
    {
        "name": "junior_embedded_good_fit",
        "job": "Junior Embedded Engineer. Need C, embedded systems, testing, and debugging on hardware.",
        "cv": "Electronic engineering graduate with C, microcontroller projects, embedded debugging, and hardware testing experience.",
        "cover": "I want this junior embedded role because I have already built and debugged embedded hardware in final-year projects.",
        "score_min": 58,
        "score_max": 86,
        "must_include": ["embedded", "testing"],
    },
    {
        "name": "senior_mechanical_excluded_for_undergrad",
        "job": "Senior Mechanical Engineer. Lead design reviews, own complex mechanisms, and mentor engineers. Requires 5+ years of experience.",
        "cv": "Mechanical engineering undergraduate with CAD, testing, manufacturing, and prototype project work.",
        "cover": "I want to build my mechanical engineering career through a role with strong design exposure.",
        "score_min": 8,
        "score_max": 35,
        "must_note": "senior",
    },
    {
        "name": "manufacturing_year_in_industry_good_fit",
        "job": "Manufacturing Year in Industry. Need lean improvement, testing, production support, and process data.",
        "cv": "Industrial engineering student with lean project work, production data analysis, and factory test support. Reduced waste by 9%.",
        "cover": "I want a year in industry role where I can contribute to lean improvement, production support, and testing.",
        "score_min": 63,
        "score_max": 90,
        "must_include": ["lean", "testing"],
    },
    {
        "name": "software_student_not_zero_for_grad_role",
        "job": "Graduate Backend Engineer. Need Python, APIs, SQL, and cloud deployment.",
        "cv": "Computer science student with Python, Flask APIs, SQL coursework, and deployed university projects.",
        "cover": "I want this backend role because I enjoy building Python APIs and deploying project work.",
        "score_min": 55,
        "score_max": 85,
        "must_include": ["python", "api"],
    },
]


def _clamp(value: int, lower: int = 0, upper: int = 100) -> int:
    return max(lower, min(value, upper))


def _variant(case: dict[str, object], suffix: str, *, job: str | None = None, cv: str | None = None, cover: str | None = None, widen: int = 6) -> dict[str, object]:
    variant = deepcopy(case)
    variant["name"] = f"{case['name']}_{suffix}"
    variant["job"] = job if job is not None else str(case["job"])
    variant["cv"] = cv if cv is not None else str(case["cv"])
    variant["cover"] = cover if cover is not None else str(case["cover"])
    variant["score_min"] = _clamp(int(case["score_min"]) - widen)
    variant["score_max"] = _clamp(int(case["score_max"]) + widen)
    return variant


def _variants_for_case(case: dict[str, object]) -> list[dict[str, object]]:
    job = str(case["job"])
    cv = str(case["cv"])
    cover = str(case["cover"])
    first_job = job.replace(". ", ".\n", 1)
    return [
        deepcopy(case),
        _variant(case, "multiline_job", job=first_job),
        _variant(case, "cv_headings", cv=f"Education\n{cv}\nProjects\nCollaborated with teams and documented progress."),
        _variant(case, "cover_headings", cover=f"Motivation\n{cover}\nEvidence\nI want to contribute quickly and learn from the team."),
        _variant(case, "structured_docs", cv=cv.replace(". ", ".\n"), cover=cover.replace(". ", ".\n")),
        _variant(case, "expanded_cv", cv=f"{cv} Worked across teams, documented results, and communicated clearly."),
        _variant(case, "expanded_cover", cover=f"{cover} I would value the chance to contribute quickly and learn from experienced engineers."),
        _variant(case, "spaced_format", job=f"  {job}  ", cv=f"\n{cv}\n", cover=f"\n{cover}\n"),
        _variant(
            case,
            "project_context",
            cv=f"{cv} Final-year project context: owned delivery, testing, and reporting.",
            cover=f"{cover} My project work gives me a solid base for this role.",
        ),
    ]


REVIEWER_CASES = [variant for case in BASE_REVIEWER_CASES for variant in _variants_for_case(case)]
