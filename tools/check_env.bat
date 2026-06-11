@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo Checking FreeLadder runtime...
echo.

FreeLadder-Console.exe --runtime-check

pause
