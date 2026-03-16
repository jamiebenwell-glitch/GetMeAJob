$ErrorActionPreference = "Stop"

$python = "C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = "src"

& $python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python tools/run_reviewer_agent.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python tools/audit_reviewer_agent.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python tools/run_milestone_agents.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $python -m getmeajob.cli company-jobs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
