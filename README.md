# GetMeAJob

Engineering jobs board, CV and cover-letter reviewer, and interview-prep workspace for UK early-career roles.

## Why not Gradcracker
Gradcracker's terms prohibit automated scraping or downloading of their site content. This project avoids scraping Gradcracker directly and uses an API-based source instead.

## Setup
1. Install Python 3.12.
2. Create a local `.env` or set environment variables directly.
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

Core environment variables:

```powershell
$env:SESSION_SECRET = "replace-with-a-long-random-secret"
$env:PUBLIC_BASE_URL = "http://127.0.0.1:8010"
$env:SESSION_HTTPS_ONLY = "0"
```

Optional environment variables:

```powershell
$env:GOOGLE_CLIENT_ID = "your_google_client_id"
$env:GOOGLE_CLIENT_SECRET = "your_google_client_secret"
$env:ADZUNA_APP_ID = "your_adzuna_app_id"
$env:ADZUNA_APP_KEY = "your_adzuna_app_key"
```

The checked-in `.env.example` shows the current app-level variables.

## Run The Web App
Use the helper script:

```powershell
./scripts/start_web.ps1
```

Open `http://127.0.0.1:8010`.

The web app supports:
- Official-source job browsing with filters and one-click handoff into review.
- Multi-application review in one workspace.
- CV and cover-letter uploads in `.txt`, `.pdf`, and `.docx`.
- Saved drafts, revision history, review history, and an evidence bank when signed in.
- Requirement-to-evidence mapping, grounded chat follow-up, and interview prep.
- Reviewer safety filters that keep demographic questionnaires and admin gate text out of requirement coaching.

Google sign-in is optional locally, but required if you want saved drafts and history tied to an account.

## Release Gate

```powershell
./scripts/run_release_checks.ps1
```

The release gate runs tests, reviewer benchmark and audit, milestone browser coverage, and refreshes the official company-feed data.

## Notes
- The filter is keyword-based. Adjust `--query` or the keywords in `src/getmeajob/providers/adzuna.py` if needed.
- Set `--country` (e.g., `us`, `gb`) and `--where` to scope locations.

## Official Company Feeds
Fetch a starter pool of UK engineering jobs from official company-hosted ATS feeds.

```powershell
$env:PYTHONPATH = "src"
python -m getmeajob.cli company-jobs
```

Outputs:
- `data/uk_engineering_company_jobs.json`
- `data/uk_engineering_company_jobs.csv`

Current starter pool:
- Gearset via Lever
- StarCompliance via Lever
- Monzo via Greenhouse
- Graphcore via Greenhouse

## CV & Cover Letter Review
Provide a job description text file plus uploaded CV and cover letter files.

```powershell
$env:PYTHONPATH = "src"
python -m getmeajob.cli review --job job.txt --cv cv.txt --cover-letter cover.txt
```

The command prints JSON with a total percentage score plus category scores and feedback.

## Hosted Deployment
Render is the recommended host for this app.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jamiebenwell-glitch/GetMeAJob)

- `Dockerfile` builds a production image.
- `render.yaml` provides a Render service definition with a health check.
- The app reads `HOST` and `PORT` from the environment for hosted runtimes.
- `GET /healthz` returns a simple readiness response for the platform health check.
- Set `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `PUBLIC_BASE_URL` in the Render dashboard.
- Keep secrets out of git and rotate any credentials that were ever pasted into chat or logs.

Example local container run:

```powershell
docker build -t getmeajob .
docker run -p 8000:8000 getmeajob
```

## Agent Setup
The repo includes an explicit multi-agent setup in `agents/`.

Core agent specs:
- `agents/source_compliance.md`
- `agents/ats_ingestion.md`
- `agents/normalization_quality.md`
- `agents/reviewer_assistant.md`
- `agents/frontend_qa.md`

Registry:
- `agents/registry.json`

