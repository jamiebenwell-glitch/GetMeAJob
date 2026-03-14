# GetMeAJob

Fetch Mechanical Engineering Year in Industry roles using a compliant API source, and review CVs/cover letters against a job post.

## Why not Gradcracker
Gradcracker's terms prohibit automated scraping or downloading of their site content. This project avoids scraping Gradcracker directly and uses an API-based source instead.

## Setup
1. Install Python 3.11+.
2. Create an Adzuna developer account and obtain `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
3. Set environment variables:

```powershell
$env:ADZUNA_APP_ID = "your_app_id"
$env:ADZUNA_APP_KEY = "your_app_key"
```

4. Install dependencies:

```powershell
pip install -r requirements.txt
```

## Run
Use the helper script (sets `PYTHONPATH=src`):

```powershell
./scripts/fetch_mech_yii.ps1
```

Or run directly:

```powershell
$env:PYTHONPATH = "src"
python -m getmeajob.cli adzuna
```

Outputs:
- `data/adzuna_mech_year_in_industry.json`
- `data/adzuna_mech_year_in_industry.csv`

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

## Web App
Run the reviewer as a web app that accepts multiple applications per submission.

```powershell
./scripts/start_web.ps1
```

Open `http://127.0.0.1:8010` in your browser.

The web app supports:
- Job advert URL input, with page text extracted when the page is publicly readable.
- CV uploads in `.txt`, `.pdf`, and `.docx`.
- Cover letter uploads in `.txt`, `.pdf`, and `.docx`.
- A tabbed reviewer/results workspace so the review stays in view after submission.
- Suggested edits with highlighted weak excerpts in the review output.
- Role suggestions based on the uploaded CV against the live jobs board.
- Automated browser tests for the upload-and-review flow and the workspace layout.

## Hosted Deployment
Render is the recommended host for this app.

- `Dockerfile` builds a production image.
- `render.yaml` provides a Render service definition with a health check.
- The app reads `HOST` and `PORT` from the environment for hosted runtimes.
- `GET /healthz` returns a simple readiness response for the platform health check.

Example local container run:

```powershell
docker build -t getmeajob .
docker run -p 8000:8000 getmeajob
```

## Agent Setup
The repo now includes an explicit multi-agent setup in `agents/`.

Core agent specs:
- `agents/source_compliance.md`
- `agents/ats_ingestion.md`
- `agents/normalization_quality.md`
- `agents/reviewer_assistant.md`
- `agents/frontend_qa.md`

Registry:
- `agents/registry.json`

Release check runner:

```powershell
./scripts/run_release_checks.ps1
```
