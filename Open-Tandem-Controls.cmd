@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run Setup-Environment.cmd first. See README.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -I -B -c "import sys,requests,tkinter; raise SystemExit(sys.version_info < (3,11))" >nul 2>nul
if errorlevel 1 (
    echo Environment is unusable or Tkinter is missing. Run Setup-Environment.cmd and see docs\TROUBLESHOOTING.md.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -B "scripts\tandem-control-panel.py"
if errorlevel 1 pause
