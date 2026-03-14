param(
    [string]$Host = "127.0.0.1",
    [int]$Port = 8010
)

$ErrorActionPreference = "Stop"

python -m pip install -r requirements.txt

$env:PYTHONPATH = "src"

Start-Process "http://$Host`:$Port"
& "C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn getmeajob.webapp:app --host $Host --port $Port
