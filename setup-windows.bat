@echo off
setlocal
cd /d "%~dp0"
if not exist data mkdir data
set "PYEXE="
for %%P in (py python "%USERPROFILE%\miniconda3\python.exe") do call :try "%%~P"
if not defined PYEXE goto :nopython
echo Using Python: %PYEXE%
set "PYRUN=%~dp0.venv\Scripts\python.exe"
if not exist "%PYRUN%" "%PYEXE%" -m venv "%~dp0.venv"
"%PYRUN%" -c "import tkinter; r = tkinter.Tk(); r.destroy()" >nul 2>&1
if errorlevel 1 goto :novenv
set "PIPARGS="
goto :install
:novenv
echo The virtual environment cannot open a Tk window, so %PYEXE% is used directly.
set "PYRUN=%PYEXE%"
set "PIPARGS=--user"
:install
"%PYRUN%" -m pip install %PIPARGS% pillow numpy websocket-client tkinterdnd2
if errorlevel 1 goto :pipfail
(echo %PYRUN%)>"%~dp0data\python.txt"
echo.
echo Creating the desktop shortcut "PhotoCraft AI" ...
"%PYRUN%" -m pccomfy shortcut
echo.
echo Setup done. Start PhotoCraft with the desktop shortcut "PhotoCraft AI" (or photocraft-ai.bat).
pause
exit /b 0

:try
if defined PYEXE exit /b 0
"%~1" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if not errorlevel 1 set "PYEXE=%~1"
exit /b 0

:nopython
echo Python 3.11 or newer with tkinter was not found.
echo Install it from python.org (tick "tcl/tk") or use miniconda, then run this again.
pause
exit /b 1

:pipfail
echo pip install failed. Check the messages above.
pause
exit /b 1
