@echo off
REM ============================================================
REM  OA Judge launcher (Windows / WSL)
REM  Starts the judge server inside WSL, then opens it in your browser.
REM  The server runs in its own window titled "OA Judge Server".
REM  Close that window (or press Ctrl+C in it) to stop the judge.
REM ============================================================
title OA Judge

REM Start the Flask server inside WSL via a single script path (no quote-nesting).
REM It binds 127.0.0.1:5137, which WSL2 forwards to Windows localhost.
start "OA Judge Server  -  close this window to stop" wsl.exe -e bash /mnt/c/Users/jishu/Desktop/oa-judge/_serve.sh

REM Give the server a few seconds to come up, then open the browser.
timeout /t 5 /nobreak >nul
start "" "http://127.0.0.1:5137"
exit
