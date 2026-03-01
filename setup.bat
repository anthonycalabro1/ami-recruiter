@echo off
echo ============================================================
echo   AMI Recruiting Automation - Setup
echo ============================================================
echo.

REM Check if Python is installed (try python first, then py launcher)
set PYTHON_CMD=python
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    set PYTHON_CMD=py
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not in your PATH.
        echo.
        echo Please install Python 3.10 or later:
        echo   1. Go to https://www.python.org/downloads/
        echo   2. Download the latest Python 3.x installer
        echo   3. IMPORTANT: Check "Add Python to PATH" during installation
        echo   4. Run this setup script again after installing
        echo.
        pause
        exit /b 1
    )
)

echo [1/3] Python found:
%PYTHON_CMD% --version
echo.

echo [2/3] Installing required packages...
echo This may take a minute...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo [ERROR] Package installation failed.
    echo Try running: pip install -r requirements.txt
    pause
    exit /b 1
)
echo.
echo [OK] Packages installed successfully.

echo.
echo [3/3] Creating folders...
if not exist "AMI_Candidates_Inbox" mkdir AMI_Candidates_Inbox
if not exist "AMI_Candidates_Processed" mkdir AMI_Candidates_Processed
if not exist "AMI_Candidates_Failed" mkdir AMI_Candidates_Failed
echo [OK] Folders created.

echo.
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Edit config.yaml and add your Anthropic API key
echo   2. Optionally add Gmail credentials for notifications
echo   3. Double-click start.bat to launch the system
echo.
pause
