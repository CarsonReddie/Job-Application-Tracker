@echo off
echo === JobTracker Windows Build ===
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Download from https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create virtual environment
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet

:: Clean previous builds
rmdir /s /q dist build 2>nul

:: Build
echo Building executable...
pyinstaller --noconfirm build.spec

:: Check if exe was built
if not exist dist\JobTracker.exe (
    echo.
    echo BUILD FAILED. Check output above for errors.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo Executable ready: dist\JobTracker.exe
echo ==========================================
echo.

:: Check for Inno Setup
set "ISCC_PATH="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 6\ISCC.exe"
) else if exist "%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles(x86)%\Inno Setup 5\ISCC.exe"
) else if exist "%ProgramFiles%\Inno Setup 5\ISCC.exe" (
    set "ISCC_PATH=%ProgramFiles%\Inno Setup 5\ISCC.exe"
)

if not "%ISCC_PATH%"=="" (
    echo Building installer...
    "%ISCC_PATH%" installer.iss
    echo.
    for %%F in (JobTracker-Setup-*.exe) do (
        echo ==========================================
        echo SETUP INSTALLER READY!
        echo ==========================================
        echo %%~fF
    )
) else (
    echo Inno Setup not found. Skipping installer build.
    echo.
    echo To build an installer:
    echo   1. Install Inno Setup from https://jrsoftware.org/isdl.php
    echo   2. Open installer.iss in Inno Setup and click Build
    echo      OR run: "C:\Program Files\Inno Setup 6\ISCC.exe" installer.iss
    echo.
    echo Or just distribute dist\JobTracker.exe standalone.
)

pause
