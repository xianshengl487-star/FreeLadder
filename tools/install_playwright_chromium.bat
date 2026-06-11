@echo off
chcp 65001 >nul
cd /d "%~dp0\.."

echo Installing Playwright Chromium for FreeLadder...
echo.

set PLAYWRIGHT_BROWSERS_PATH=%CD%\ms-playwright

if not exist "ms-playwright" mkdir ms-playwright

python -m playwright install chromium

if %errorlevel% neq 0 (
    echo.
    echo 安装失败。请确保已安装 Python 和 Playwright:
    echo   pip install playwright
    echo   playwright install chromium
    echo.
) else (
    echo.
    echo Done.
)

pause
