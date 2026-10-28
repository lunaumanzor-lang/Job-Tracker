@echo off
title Smart Job Tracker
cd /d %~dp0
echo Iniciando Smart Job Tracker...
.venv\Scripts\streamlit.exe run app.py
pause
