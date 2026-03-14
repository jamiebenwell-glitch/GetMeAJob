@echo off
setlocal

set PORT=8010
set PYTHON_EXE=C:\Users\Jamie\AppData\Local\Programs\Python\Python312\python.exe
%PYTHON_EXE% -m pip install -r requirements.txt
set PYTHONPATH=src
start http://127.0.0.1:%PORT%
%PYTHON_EXE% -m uvicorn getmeajob.webapp:app --host 127.0.0.1 --port %PORT%
