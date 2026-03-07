@echo off
setlocal enabledelayedexpansion

echo.
echo  =======================================================
echo   Couch Control - Windows Installer
echo  =======================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Download from https://python.org
    pause
    exit /b 1
)
echo [OK] Python found

:: Install Python dependencies
echo.
echo [*] Installing Python dependencies...
pip install aiohttp mss Pillow PyYAML netifaces pynput websockets
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed

:: Optional: pystray for system tray
echo.
echo [*] Installing optional system tray support...
pip install pystray >nul 2>&1
if errorlevel 1 (
    echo [INFO] pystray not installed - system tray will be disabled
) else (
    echo [OK] System tray support installed
)

:: Install couch-control package
echo.
echo [*] Installing Couch Control...
pip install -e "%~dp0."
if errorlevel 1 (
    echo [ERROR] Failed to install Couch Control
    pause
    exit /b 1
)
echo [OK] Couch Control installed

:: Ask about startup
echo.
set /p STARTUP="Start Couch Control automatically at Windows login? (y/n): "
if /i "!STARTUP!"=="y" (
    echo [*] Setting up startup task...

    :: Find python executable
    for /f "tokens=*" %%i in ('where python') do set PYTHON_PATH=%%i

    :: Create Task Scheduler entry (no UAC required for current user)
    schtasks /create /tn "Couch Control" ^
        /tr "\"!PYTHON_PATH!\" -m couch_control start" ^
        /sc onlogon ^
        /rl limited ^
        /f >nul 2>&1

    if errorlevel 1 (
        :: Fallback: add to startup folder
        set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
        echo @echo off > "!STARTUP_FOLDER!\couch-control.bat"
        echo python -m couch_control start >> "!STARTUP_FOLDER!\couch-control.bat"
        echo [OK] Added to startup folder: !STARTUP_FOLDER!
    ) else (
        echo [OK] Startup task created via Task Scheduler
    )
)

:: Ask about PIN
echo.
set /p SET_PIN="Set a PIN for security? (leave blank to skip): "
if not "!SET_PIN!"=="" (
    set CONFIG_DIR=%USERPROFILE%\.config\couch-control
    if not exist "!CONFIG_DIR!" mkdir "!CONFIG_DIR!"

    (
        echo server:
        echo   port: 8080
        echo   host: "0.0.0.0"
        echo security:
        echo   pin: "!SET_PIN!"
    ) > "!CONFIG_DIR!\config.yaml"

    echo [OK] PIN saved to !CONFIG_DIR!\config.yaml
)

:: Create desktop shortcut
echo.
set DESKTOP=%USERPROFILE%\Desktop
set SHORTCUT=%DESKTOP%\Couch Control.bat
(
    echo @echo off
    echo echo Starting Couch Control...
    echo python -m couch_control start --tray
    echo pause
) > "%SHORTCUT%"
echo [OK] Desktop shortcut created: %SHORTCUT%

echo.
echo  =======================================================
echo   Installation complete!
echo.
echo   Start:  python -m couch_control start
echo   Stop:   python -m couch_control stop
echo   Status: python -m couch_control status
echo.
echo   Or double-click "Couch Control.bat" on your Desktop.
echo  =======================================================
echo.

set /p START_NOW="Start Couch Control now? (y/n): "
if /i "!START_NOW!"=="y" (
    python -m couch_control start --tray
)

pause
