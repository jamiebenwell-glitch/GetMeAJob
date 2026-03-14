$ErrorActionPreference = "Stop"

$python = "C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = "src"

& $python -m pytest -q
& $python -m getmeajob.cli company-jobs
