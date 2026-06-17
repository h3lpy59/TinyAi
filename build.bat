@echo off
echo ========================================
echo   TinyAI - Build Script
echo ========================================
echo.

echo [1/3] Installing dependencies...
python -m pip install requests pyinstaller --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip failed. Make sure Python is installed.
    pause & exit /b 1
)

echo [2/3] Compiling to TinyAI.exe ...
python -m PyInstaller --onefile --console --name TinyAI tinyai.py
if %errorlevel% neq 0 (
    echo ERROR: Build failed.
    pause & exit /b 1
)

echo [3/3] Done!
echo.
echo  Your exe is at:  dist\TinyAI.exe
echo.
pause
