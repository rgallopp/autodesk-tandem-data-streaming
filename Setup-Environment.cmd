@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 -B scripts\setup_environment.py
goto result
:python
python -B scripts\setup_environment.py
:result
if errorlevel 1 goto failed
echo Ready. Open Open-Tandem-Controls.cmd to preview or send.
pause
exit /b 0
:failed
echo Setup failed. Install Python 3.11 or later with pip, then see docs\TROUBLESHOOTING.md.
pause
exit /b 1
