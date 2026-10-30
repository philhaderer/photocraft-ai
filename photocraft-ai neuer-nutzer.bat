@echo off
setlocal
cd /d "%~dp0"
rem Test start as a NEW USER: the plugin gets its own data folder (data\neuer-nutzer) instead of data\, so it knows
rem nothing of your settings, presets and last model. Your real data folder is not touched.
rem Option "without models": the plugin acts as if ComfyUI had no model files (ComfyUI itself is not changed).
rem Close PhotoCraft first: it is started here with the test folder's own token and exchange folder.
if not defined PHOTOCRAFT set "PHOTOCRAFT=C:\programs\photocraft-0.17.0-windows-x64-portable\photocraft.exe"
if not defined PCC_PORT set "PCC_PORT=7878"
set "DATA=%~dp0data\neuer-nutzer"
set "XCH=%DATA%\exchange"

if not exist "%PHOTOCRAFT%" goto :nophotocraft
if not exist "%~dp0data\python.txt" goto :nosetup
set /p PY=<"%~dp0data\python.txt"

powershell -NoProfile -Command "try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PCC_PORT%);$c.Close();exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto :running

echo Test start as a new user
echo   1 = new user, first start (the test folder is emptied)
echo   2 = same test user, next start (keeps what the first start saved)
echo   3 = new user, first start, ComfyUI WITHOUT models
echo   4 = same test user, next start, ComfyUI WITHOUT models
choice /c 1234 /n /m "Choose 1-4: "
set "PICK=%errorlevel%"
if "%PICK%"=="1" set "FRESH=1"
if "%PICK%"=="3" set "FRESH=1"
if "%PICK%"=="3" set "PCCOMFY_SIMULATE_NO_MODELS=1"
if "%PICK%"=="4" set "PCCOMFY_SIMULATE_NO_MODELS=1"
if defined FRESH if exist "%DATA%" rd /s /q "%DATA%"
if not exist "%XCH%" mkdir "%XCH%"
set "PCCOMFY_HOME=%DATA%"

start "" "%PHOTOCRAFT%" --control %PCC_PORT% --control-token-file "%DATA%\photocraft.token" --automation-read-root "%XCH%" --automation-write-root "%XCH%" %*
powershell -NoProfile -Command "for($i=0;$i -lt 150;$i++){try{$c=New-Object Net.Sockets.TcpClient('127.0.0.1',%PCC_PORT%);$c.Close();exit 0}catch{Start-Sleep -Milliseconds 200}};exit 1"
if errorlevel 1 goto :noport

"%PY%" -m pccomfy
if errorlevel 1 pause
exit /b 0

:running
echo PhotoCraft is already running. Close it first: the test start opens it with the test folder.
pause
exit /b 1

:nophotocraft
echo PhotoCraft not found: %PHOTOCRAFT%
pause
exit /b 1

:nosetup
echo Run setup-windows.bat first.
pause
exit /b 1

:noport
echo PhotoCraft did not open the control port %PCC_PORT%.
pause
exit /b 1
