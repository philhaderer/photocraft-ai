@echo off
setlocal
cd /d "%~dp0"
if not exist "data\python.txt" (echo Run setup-windows.bat first.& pause & exit /b 1)
set /p PY=<"data\python.txt"
echo ---- check ----
"%PY%" -m pccomfy check
echo.
echo ---- probe ----
"%PY%" -m pccomfy probe
echo.
pause
