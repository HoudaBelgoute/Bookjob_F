@echo off
REM Lance BookJob (API + interface) sur http://localhost:8000
cd /d "%~dp0frontend"
if not exist node_modules ( npm install )
if errorlevel 1 exit /b 1
call npm run build
if errorlevel 1 exit /b 1
cd /d "%~dp0backend"
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -q -r requirements.txt
if exist .env ( for /f "usebackq tokens=1,* delims==" %%a in (".env") do if not "%%a"=="" if not "%%b"=="" set "%%a=%%b" )
start "" http://localhost:8000
python -m uvicorn app.main:app --port 8000
