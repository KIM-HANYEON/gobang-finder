@echo off
setlocal
REM 방극 원문 -> formulas.json 생성

cd /d "%~dp0"
python "%~dp0build_data.py"

echo.
echo 완료되었습니다. 창을 닫아도 됩니다.
pause
