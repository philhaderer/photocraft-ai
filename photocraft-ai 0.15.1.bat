@echo off
setlocal
cd /d "%~dp0"
rem Starts PhotoCraft with the control channel for the ComfyUI bridge, then opens the bridge window.
rem Close PhotoCraft first if it is already running without --control.
rem Environment overrides: PHOTOCRAFT (path to photocraft.exe), PCC_PORT (default 7878)
if not defined PHOTOCRAFT set "PHOTOCRAFT=C:\programs\photocraft-0.15.1-windows-x64-portable\photocraft.exe"
if not defined PCC_PORT set "PCC_PORT=7878"
set "DATA=%~dp0data"
set "XCH=%DATA%\exchange"

if not exist "%PHOTOCRAFT%" goto :nophotocraft
if not exist "%DATA%\python.txt" goto :nosetup
set /p PY=<"%DATA%\python.txt"
if not exist "%XCH%" mkdir "%XCH%"

powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PCC_PORT%);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto :gui

start "" "%PHOTOCRAFT%" --control %PCC_PORT% --control-token-file "%DATA%\photocraft.token" --automation-read-root "%XCH%" --automation-write-root "%XCH%" %*
powershell -NoProfile -Command "for($i=0;$i -lt 150;$i++){try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PCC_PORT%);$c.Close();exit 0}catch{Start-Sleep -Milliseconds 200}};exit 1"
if errorlevel 1 goto :noport

:gui
"%PY%" -m pccomfy
if errorlevel 1 pause
exit /b 0

:nophotocraft
echo PhotoCraft not found: %PHOTOCRAFT%
pause
exit /b 1

:nosetup
echo Run setup-windows.bat first.
pause
exit /b 1

:noport
echo PhotoCraft did not open the control port %PCC_PORT%. Is another PhotoCraft instance already running?
pause
exit /b 1
