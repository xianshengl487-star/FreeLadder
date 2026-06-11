@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

if not exist "config.yaml" (
    copy "config.example.yaml" "config.yaml"
)

notepad config.yaml
