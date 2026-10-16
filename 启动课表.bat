@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" goto noenv
"venv\Scripts\python.exe" service.py start %*
if errorlevel 1 pause
exit /b

:noenv
echo.
echo  [X] Virtual environment not found: venv\Scripts\python.exe
echo      Please do the "Install" steps in README.md first, then run this again.
echo.
pause
exit /b 1
