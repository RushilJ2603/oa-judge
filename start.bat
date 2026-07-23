@echo off
REM OA Judge launcher (native Windows). Requires Python with Flask + a g++ (e.g. MinGW) on PATH.
cd /d "%~dp0"
set OAJ_PORT=5137
start "" http://127.0.0.1:5137
python app\server.py
