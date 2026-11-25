@echo off
setlocal
chcp 65001 >nul

set "BUILD_DIR=%~dp0"
if "%BUILD_DIR:~-1%"=="\" set "BUILD_DIR=%BUILD_DIR:~0,-1%"
cd /d "%BUILD_DIR%"

echo Checking Python and PyInstaller...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found in PATH.
    if not "%~1"=="--ci" pause
    exit /b 1
)
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PyInstaller is not installed. Run: pip install pyinstaller
    if not "%~1"=="--ci" pause
    exit /b 1
)

echo Cleaning previous build/dist artifacts...
if exist "%BUILD_DIR%\build" rmdir /s /q "%BUILD_DIR%\build"
if exist "%BUILD_DIR%\dist" rmdir /s /q "%BUILD_DIR%\dist"

echo Running PyInstaller...
python -m PyInstaller --noconfirm --clean --distpath "%BUILD_DIR%\dist" --workpath "%BUILD_DIR%\build" "%BUILD_DIR%\SPAudioTruth.spec"
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed with code %errorlevel%.
    if not "%~1"=="--ci" pause
    exit /b %errorlevel%
)

echo Cleaning temporary build directory...
if exist "%BUILD_DIR%\build" rmdir /s /q "%BUILD_DIR%\build"

if not exist "%BUILD_DIR%\dist\SPAudioTruth\SPAudioTruth.exe" (
    echo [ERROR] Output binary not found: "%BUILD_DIR%\dist\SPAudioTruth\SPAudioTruth.exe"
    if not "%~1"=="--ci" pause
    exit /b 1
)

echo.
echo Build completed: "%BUILD_DIR%\dist\SPAudioTruth\SPAudioTruth.exe"
if exist "%BUILD_DIR%\dist\SPAudioTruth\_internal\bin" (
    echo Bundled binaries in _internal\bin:
    dir /b "%BUILD_DIR%\dist\SPAudioTruth\_internal\bin"
)
echo.

if not "%~1"=="--ci" (
    explorer "%BUILD_DIR%\dist\SPAudioTruth"
    pause
)
