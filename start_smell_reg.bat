@echo off
title Smell-Reg - Fragrance Regulatory Compliance
cd /d C:\Users\pwong\projects\smell-reg
call .venv\Scripts\activate
echo.
echo ========================================
echo   Smell-Reg - Regulatory Compliance
echo ========================================
echo.
echo Starting Streamlit UI at http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

REM Open browser after delay (in background)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:8501"

REM Start Streamlit
.venv\Scripts\streamlit.exe run ui/app.py --server.port 8501
