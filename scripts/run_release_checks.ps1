$ErrorActionPreference = "Stop"

$python = "C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = "src"

& $python -m pytest -q
& $python tools/run_reviewer_agent.py
& $python tools/audit_reviewer_agent.py
& $python tools/run_milestone_agents.py
& $python -m getmeajob.cli company-jobs
