@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo FreeLadder
echo ========================================
echo.

if not exist "config.yaml" (
    if exist "config.example.yaml" (
        copy "config.example.yaml" "config.yaml" >nul
        echo Created config.yaml from config.example.yaml
    )
)

if not exist "data" mkdir data
if not exist "exports" mkdir exports
if not exist "logs" mkdir logs
if not exist "bin" mkdir bin

start "" "%~dp0FreeLadder.exe"
