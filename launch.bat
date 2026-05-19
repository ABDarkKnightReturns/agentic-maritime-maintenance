@echo off
title MV-Callisto — AI Predictive Maintenance
cd /d "C:\Users\abhis\maritime-maintenance-demo"

echo.
echo  ========================================
echo   MV-Callisto — AI Predictive Maintenance
echo   NordVast Maritime Fleet Management
echo  ========================================
echo.
echo  Starting Streamlit app...
echo  Browser will open at http://localhost:8501
echo.

"C:\Users\abhis\.conda\envs\Maritime-demo\Scripts\streamlit.exe" run app.py --server.port 8501 --server.headless false

pause
