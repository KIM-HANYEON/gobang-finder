@echo off
setlocal
cd /d "%~dp0"
start "" pythonw "%~dp0main.py"
if errorlevel 1 start "" python "%~dp0main.py"
