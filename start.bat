@echo off
echo ============================================================
echo   AMI Recruiting Automation - Starting...
echo ============================================================
echo.

REM Check if setup has been run
if not exist "AMI_Candidates_Inbox" (
    echo [ERROR] Setup has not been run yet.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

REM Determine Python command (try python first, then py)
REM Suppress "Could not find platform independent libraries" warning from Python 3.14
set PYTHONNOUSERSITE=1
set PYTHON_CMD=python
%PYTHON_CMD% --version >nul 2>&1
if errorlevel 1 (
    set PYTHON_CMD=py
    py --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python is not installed or not in your PATH.
        echo Please run setup.bat first.
        pause
        exit /b 1
    )
)

REM Check config
%PYTHON_CMD% -c "import yaml; c=yaml.safe_load(open('config.yaml')); assert not c['anthropic_api_key'].startswith('YOUR_'), 'API key not configured'" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Anthropic API key not configured.
    echo Please edit config.yaml and add your API key.
    echo Get one at: https://console.anthropic.com
    pause
    exit /b 1
)

echo Starting Dashboard (opens in your browser)...
start "AMI Dashboard" cmd /c "set PYTHONNOUSERSITE=1 && %PYTHON_CMD% -m streamlit run dashboard.py --server.port 8501 2>nul"

echo.
echo Waiting for dashboard to start...
timeout /t 5 /nobreak >nul
start http://localhost:8501

echo Starting Processing Pipeline...
echo.
echo ============================================================
echo   System is running!
echo ============================================================
echo.
echo   Dashboard: http://localhost:8501 (should open automatically)
echo   Inbox:     AMI_Candidates_Inbox (drop resumes here)
echo.
echo   Press Ctrl+C to stop the processing pipeline.
echo   Close the dashboard window separately.
echo ============================================================
echo.

%PYTHON_CMD% pipeline.py 2>&1 | findstr /V "Could not find platform independent libraries"
