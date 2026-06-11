@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo Checking FreeLadder runtime...
echo.

if exist "FreeLadder-Console.exe" (
    "FreeLadder-Console.exe" --runtime-check
) else if exist "..\FreeLadder-Console\FreeLadder-Console.exe" (
    "..\FreeLadder-Console\FreeLadder-Console.exe" --runtime-check
) else (
    echo FreeLadder-Console.exe not found.
    echo Please run FreeLadder.exe directly or rebuild the package.
)

pause
