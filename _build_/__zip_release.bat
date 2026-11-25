@echo off
setlocal
chcp 65001 >nul

set "BUILD_DIR=%~dp0"
if "%BUILD_DIR:~-1%"=="\" set "BUILD_DIR=%BUILD_DIR:~0,-1%"
cd /d "%BUILD_DIR%"

set "DIST_DIR=%BUILD_DIR%\dist\SPAudioTruth"
if not exist "%DIST_DIR%\SPAudioTruth.exe" (
    echo [ERROR] Build not found at "%DIST_DIR%\SPAudioTruth.exe". Run __build.bat first.
    if not "%~1"=="--ci" pause
    exit /b 1
)

set "VERSION_FILE=%BUILD_DIR%\..\src\version.txt"
set "VERSION=1.0.0"
if exist "%VERSION_FILE%" (
    set /p VERSION=<"%VERSION_FILE%"
)

set "ZIP_PATH=%BUILD_DIR%\SPAudioTruth_v%VERSION%.zip"
if exist "%ZIP_PATH%" del /f /q "%ZIP_PATH%"

echo Packaging "%DIST_DIR%" into "%ZIP_PATH%" (deflate level 9)...
python -c "import os, zipfile; src=r'%DIST_DIR%'; dst=r'%ZIP_PATH%'; zf=zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED, compresslevel=9); [zf.write(os.path.join(r, f), os.path.relpath(os.path.join(r, f), os.path.dirname(src))) for r, _, fs in os.walk(src) for f in fs]; zf.close(); print(f'Created: {dst} ({os.path.getsize(dst)/(1024*1024):.2f} MB)')"
if errorlevel 1 (
    echo [ERROR] Failed to create release archive.
    if not "%~1"=="--ci" pause
    exit /b 1
)

if not "%~1"=="--ci" pause
