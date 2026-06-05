@echo off
echo.
echo ========================================
echo   Signal Engine v5 - Starting...
echo ========================================
echo.

REM Clear old tunnel log
del /f /q "%TEMP%\cf.log" 2>nul

REM Start cloudflared tunnel in background
echo Starting tunnel...
start /b cloudflared tunnel ^
  --url http://localhost:8000 ^
  --logfile "%TEMP%\cf.log"

REM Wait for tunnel to initialize
echo Waiting for tunnel URL...
timeout /t 8 /nobreak >nul

REM Start the bot
echo Starting Signal Engine...
python main.py