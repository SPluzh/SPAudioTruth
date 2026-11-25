$ErrorActionPreference = "Stop"

$BuildDir = $PSScriptRoot
Set-Location $BuildDir

Write-Host "Cleaning previous build/dist artifacts..." -ForegroundColor Cyan
if (Test-Path "$BuildDir\build") {
    Remove-Item -Recurse -Force "$BuildDir\build"
}
if (Test-Path "$BuildDir\dist") {
    Remove-Item -Recurse -Force "$BuildDir\dist"
}

Write-Host "Running PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean --distpath "$BuildDir\dist" --workpath "$BuildDir\build" "$BuildDir\SPAudioTruth.spec"

if (Test-Path "$BuildDir\build") {
    Remove-Item -Recurse -Force "$BuildDir\build"
}

Write-Host "Build completed: $BuildDir\dist\SPAudioTruth\SPAudioTruth.exe" -ForegroundColor Green
Get-ChildItem "$BuildDir\dist\SPAudioTruth\_internal\bin" | Select-Object Name, Length
