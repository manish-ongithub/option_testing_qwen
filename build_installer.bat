@echo off
REM ============================================
REM Smart Options Screener - Windows Build Script
REM ============================================

echo.
echo ========================================
echo   Smart Options Screener Build Script
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
echo [1/5] Activating virtual environment...
call venv\Scripts\activate

REM Install/upgrade dependencies
echo [2/5] Installing dependencies...
pip install --upgrade pip
pip install -r venv_requirements.txt
pip install pyinstaller

REM Clean previous builds
echo [3/5] Cleaning previous builds...
if exist "build" rmdir /s /q build
if exist "dist" rmdir /s /q dist

REM Build with PyInstaller
echo [4/5] Building with PyInstaller...
pyinstaller OptionsScreener.spec

if errorlevel 1 (
    echo.
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b 1
)

REM Create installer output directory
echo [5/5] Preparing installer directory...
if not exist "installer\output" mkdir installer\output

echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo Executable location:
echo   dist\OptionsScreener\OptionsScreener.exe
echo.
echo Next steps:
echo   1. Test the executable by running:
echo      dist\OptionsScreener\OptionsScreener.exe
echo.
echo   2. Create installer:
echo      - Install Inno Setup from https://jrsoftware.org/isdl.php
echo      - Open: installer\OptionsScreener_Setup.iss
echo      - Click Build ^> Compile
echo.
echo   3. Installer will be created at:
echo      installer\output\OptionsScreener_Setup_v3.3.exe
echo.
pause

