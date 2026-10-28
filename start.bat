@echo off
REM Starts the API, the live IoT simulator and the web app in three windows.
cd /d "%~dp0"

start "EcoSphere API (Django :8010)" cmd /k ".venv\Scripts\python.exe backend\manage.py runserver 127.0.0.1:8010"
timeout /t 3 /nobreak >nul
start "EcoSphere IoT simulator" cmd /k ".venv\Scripts\python.exe backend\manage.py simulate --interval 60"
start "EcoSphere Web (Vite :5173)" cmd /k "cd frontend && npm run dev"
timeout /t 5 /nobreak >nul
start "" http://localhost:5173
