@echo off
title Vidyakashi OMR Evaluation Website
cd /d "%~dp0"
echo Starting Vidyakashi OMR Evaluation Website on http://127.0.0.1:8000 ...
start "" "http://127.0.0.1:8000"
"C:\Users\rahul\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
pause
