@echo off
REM One-time setup: Python virtual environment, dependencies, database and demo data.
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe (
  echo Creating Python virtual environment...
  python -m venv .venv || goto :error
)
echo Installing backend dependencies...
.venv\Scripts\python.exe -m pip install -q -r backend\requirements.txt || goto :error

echo Preparing database...
.venv\Scripts\python.exe backend\manage.py migrate || goto :error
.venv\Scripts\python.exe backend\manage.py seed_demo --reset || goto :error

echo Installing frontend dependencies...
pushd frontend
call npm install || (popd & goto :error)
popd

echo.
echo Setup complete. Run start.bat to launch EcoSphere AI.
pause
exit /b 0

:error
echo.
echo Setup failed - see the message above.
pause
exit /b 1
