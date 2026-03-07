@echo off
setlocal

echo.
echo  =====================================================
echo   Couch Control - Windows Build
echo  =====================================================
echo.

:: Install PyInstaller
echo [*] Installing PyInstaller...
pip install --upgrade pip pyinstaller aiohttp mss Pillow PyYAML netifaces pynput
if errorlevel 1 ( echo [ERROR] Failed to install dependencies & pause & exit /b 1 )

:: Clean previous build
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist
if exist couch-control.spec del couch-control.spec

:: Build
echo.
echo [*] Building executable...
pyinstaller ^
    --onefile ^
    --name couch-control ^
    --add-data "couch_control\static;couch_control\static" ^
    --hidden-import aiohttp ^
    --hidden-import mss ^
    --hidden-import PIL ^
    --hidden-import yaml ^
    --hidden-import netifaces ^
    --hidden-import pynput.keyboard ^
    --hidden-import pynput.mouse ^
    main.py

if errorlevel 1 ( echo [ERROR] Build failed & pause & exit /b 1 )

:: Rename with platform suffix
move dist\couch-control.exe dist\couch-control-windows.exe

:: Checksum
certutil -hashfile dist\couch-control-windows.exe SHA256 > dist\couch-control-windows.sha256

echo.
echo  =====================================================
echo   Build complete!
echo.
echo   Binary:   dist\couch-control-windows.exe
echo   Checksum: dist\couch-control-windows.sha256
echo.
echo   Run it:
echo     dist\couch-control-windows.exe start
echo     dist\couch-control-windows.exe start --pin 1234
echo     dist\couch-control-windows.exe start --cloudflare --pin 1234
echo  =====================================================
echo.
pause
