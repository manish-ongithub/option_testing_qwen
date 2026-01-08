@echo off
REM ============================================
REM Build Both Applications - Windows Build Script
REM ============================================

echo.
echo ========================================
echo   Building All Applications
echo ========================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [!] Virtual environment not found. Creating one...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        pause
        exit /b 1
    )
)

REM Activate virtual environment
echo [1/6] Activating virtual environment...
call venv\Scripts\activate

REM Install/upgrade dependencies
echo [2/6] Installing dependencies...
pip install --upgrade pip
pip install -r venv_requirements.txt
pip install -r paper_trade_app/requirements.txt
pip install pyinstaller

REM Clean previous builds
echo [3/6] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build Options Screener
echo [4/6] Building Options Screener...
pyinstaller OptionsScreener.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Options Screener build failed!
    pause
    exit /b 1
)

REM Build Paper Trade App
echo [5/6] Building Paper Trade App...
pyinstaller PaperTradeApp.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Paper Trade App build failed!
    pause
    exit /b 1
)

REM Create installer output directory
echo [6/6] Preparing installer directory...
if not exist "installer\output" mkdir installer\output

echo.
echo ========================================
echo   ALL BUILDS COMPLETE!
echo ========================================
echo.
echo Executables created:
echo   1. dist\OptionsScreener\OptionsScreener.exe
echo   2. dist\PaperTradeApp\PaperTradeApp.exe
echo.
echo Next steps - Create installers:
echo   1. Install Inno Setup from https://jrsoftware.org/isdl.php
echo.
echo   2. For Options Screener:
echo      - Open: installer\OptionsScreener_Setup.iss
echo      - Build ^> Compile
echo      - Output: installer\output\OptionsScreener_Setup_v3.3.exe
echo.
echo   3. For Paper Trade App:
echo      - Open: installer\PaperTradeApp_Setup.iss
echo      - Build ^> Compile
echo      - Output: installer\output\PaperTradeApp_Setup_v1.0.exe
echo.
pause

