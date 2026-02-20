@echo off
setlocal

echo ================================================
echo  Warehouse Tracker - Task Scheduler Setup
echo ================================================
echo.
echo This registers two daily Task Scheduler tasks:
echo   WarehouseTracker_Morning   -- 5:30 AM  Mon-Thu
echo   WarehouseTracker_Afternoon -- 4:15 PM  Mon-Thu
echo.
echo NOTE: No administrator rights required (tasks run as current user).
echo.

:: --- Paths ---
set PYTHON=C:\Users\mitch\AppData\Local\Python\pythoncore-3.14-64\python.exe
set SCRIPT=%~dp0shipstation_tracker.py

:: Verify python exists
if not exist "%PYTHON%" (
    echo ERROR: Python not found at:
    echo   %PYTHON%
    echo Edit the PYTHON variable in this script to match your installation.
    pause
    exit /b 1
)

:: Verify script exists
if not exist "%SCRIPT%" (
    echo ERROR: Script not found at:
    echo   %SCRIPT%
    pause
    exit /b 1
)

:: Verify .env exists
if not exist "%~dp0.env" (
    echo WARNING: No .env file found in %~dp0
    echo Copy .env.example to .env and add your SHIPSTATION_API_KEY before the tasks run.
    echo.
)

echo [1/2] Registering WarehouseTracker_Morning (5:30 AM Mon-Thu)...
schtasks /Create /F /TN "WarehouseTracker_Morning" ^
    /TR "\"%PYTHON%\" \"%SCRIPT%\" --mode morning" ^
    /SC WEEKLY ^
    /D MON,TUE,WED,THU ^
    /ST 05:30 ^
    /RL HIGHEST
if errorlevel 1 (
    echo ERROR: Failed to create morning task.
    pause
    exit /b 1
)
echo   OK.

echo [2/2] Registering WarehouseTracker_Afternoon (4:15 PM Mon-Thu)...
schtasks /Create /F /TN "WarehouseTracker_Afternoon" ^
    /TR "\"%PYTHON%\" \"%SCRIPT%\" --mode afternoon" ^
    /SC WEEKLY ^
    /D MON,TUE,WED,THU ^
    /ST 16:15 ^
    /RL HIGHEST
if errorlevel 1 (
    echo ERROR: Failed to create afternoon task.
    pause
    exit /b 1
)
echo   OK.

echo.
echo ================================================
echo  Setup complete!
echo ================================================
echo.
echo Tasks registered:
schtasks /Query /TN "WarehouseTracker_Morning"  /FO LIST 2>nul | findstr /C:"Task Name" /C:"Next Run"
schtasks /Query /TN "WarehouseTracker_Afternoon" /FO LIST 2>nul | findstr /C:"Task Name" /C:"Next Run"
echo.
echo To remove tasks later, run:
echo   schtasks /Delete /TN "WarehouseTracker_Morning"   /F
echo   schtasks /Delete /TN "WarehouseTracker_Afternoon" /F
echo.
pause
