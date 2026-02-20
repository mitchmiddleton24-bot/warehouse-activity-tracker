@echo off
setlocal

echo ================================================
echo  Warehouse Activity Tracker -- Build Script
echo ================================================

:: Install / upgrade dependencies
echo [1/2] Installing dependencies...
pip install --upgrade -r requirements.txt
if errorlevel 1 (
    echo ERROR: pip install failed.
    pause
    exit /b 1
)

:: Build the exe
echo [2/2] Building WarehouseTracker.exe ...
pyinstaller tracker.spec --noconfirm
if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Build complete!
echo Output: dist\WarehouseTracker.exe
echo.
echo To deploy: copy dist\WarehouseTracker.exe to the target machine and run it once.
echo The app will register itself to auto-start with Windows (no admin required).
pause
